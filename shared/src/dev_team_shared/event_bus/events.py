"""대화 이벤트 Pydantic 스키마 — chat / assignment / A2A 3 layer.

publisher (UG / 에이전트 / Primary 등) 와 consumer (Chronicler) 가 공유하는
contract. event_id 는 idempotency key — 재시도 시 중복 방지.

#75 재설계로 layer 별 이벤트 분리:

- **Chat layer** (UG publish): `chat.session.start` / `chat.append` /
  `chat.session.end`
- **Assignment layer** (P/A publish): `assignment.create` /
  `assignment.update`
- **A2A layer** (각 에이전트 A2A handler publish): `a2a.context.start` /
  `a2a.message.append` / `a2a.task.create` / `a2a.task.status_update` /
  `a2a.task.artifact` / `a2a.context.end`

각 이벤트는 자기 layer 의 서버측 영속처에 1:1 매핑 (Doc Store sessions / chats /
assignments / a2a_contexts / a2a_messages / a2a_tasks /
a2a_task_status_updates / a2a_task_artifacts).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

EventType = Literal[
    # Chat layer
    "chat.session.start",
    "chat.append",
    "chat.session.end",
    # Assignment layer
    "assignment.create",
    "assignment.update",
    # A2A layer
    "a2a.context.start",
    "a2a.message.append",
    "a2a.task.create",
    "a2a.task.status_update",
    "a2a.task.artifact",
    "a2a.context.end",
]


def _utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


class _EventBase(BaseModel):
    """모든 이벤트의 공통 머리.

    - `event_id` — idempotency key (consumer 가 중복 처리 안 하도록)
    - `timestamp` — publisher 측 wall-clock
    """

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=_utc_now)


# ─────────────────────────────────────────────────────────────────────────────
#  Chat layer (UG↔P/A) — UG publish
# ─────────────────────────────────────────────────────────────────────────────


class ChatSessionStartEvent(_EventBase):
    """사용자가 새 chat session 시작.

    `session_id` 는 publisher (UG) 가 생성한 server-side session UUID. PR 1 의
    Doc Store `sessions` 테이블의 row id 와 1:1.
    """

    event_type: Literal["chat.session.start"] = "chat.session.start"
    session_id: UUID
    agent_endpoint: str                              # 'primary' | 'architect'
    initiator: str = "user"
    counterpart: str                                 # agent name
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatAppendEvent(_EventBase):
    """session 안의 한 발화 (user / agent / system).

    `session_id` 로 어느 chat session 인지, optional `prev_chat_id` 로 chain.
    """

    event_type: Literal["chat.append"] = "chat.append"
    session_id: UUID
    role: Literal["user", "agent", "system"]
    sender: str                                      # 'user' / 'primary' / ...
    content: list[dict[str, Any]] | dict[str, Any]   # A2A parts 형태
    message_id: str | None = None                    # FE / server 발급
    prev_chat_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatSessionEndEvent(_EventBase):
    """chat session 종료. UG 가 페이지 닫힘 / TTL / 명시 종료 시 publish."""

    event_type: Literal["chat.session.end"] = "chat.session.end"
    session_id: UUID
    reason: str = "completed"                        # 'completed' | 'closed' | ...
    metadata: dict[str, Any] = Field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
#  Assignment layer — P/A publish
# ─────────────────────────────────────────────────────────────────────────────


class AssignmentCreateEvent(_EventBase):
    """P / A 가 chat 중 합의된 work item 발급."""

    event_type: Literal["assignment.create"] = "assignment.create"
    assignment_id: UUID                              # publisher 가 미리 결정 (또는 처리 후 채움)
    title: str
    description: str | None = None
    status: Literal["open", "in_progress", "done", "cancelled"] = "open"
    owner_agent: str | None = None
    root_session_id: UUID | None = None              # 어느 chat session 발
    issue_refs: list[UUID] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AssignmentUpdateEvent(_EventBase):
    """assignment status / metadata 갱신.

    publisher 가 변경하고 싶은 필드만 채움 (None / 미설정 = 변경 X).
    """

    event_type: Literal["assignment.update"] = "assignment.update"
    assignment_id: UUID
    title: str | None = None
    description: str | None = None
    status: Literal["open", "in_progress", "done", "cancelled"] | None = None
    owner_agent: str | None = None
    root_session_id: UUID | None = None
    issue_refs: list[UUID] | None = None
    metadata: dict[str, Any] | None = None


# ─────────────────────────────────────────────────────────────────────────────
#  A2A layer — 각 에이전트 A2A handler publish
# ─────────────────────────────────────────────────────────────────────────────


class A2AContextStartEvent(_EventBase):
    """A2A 첫 호출 시 — counterpart 가 받음. context_id (wire) 는 호출자가 발급."""

    event_type: Literal["a2a.context.start"] = "a2a.context.start"
    context_id: str                                  # A2A wire contextId
    initiator_agent: str
    counterpart_agent: str
    parent_session_id: UUID | None = None            # session 발일 때
    parent_assignment_id: UUID | None = None         # assignment 진행 발일 때
    trace_id: str | None = None
    topic: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class A2AMessageAppendEvent(_EventBase):
    """A2A Message 송수신. trivial 응답 / Task.history 둘 다."""

    event_type: Literal["a2a.message.append"] = "a2a.message.append"
    context_id: str                                  # A2A wire contextId — chronicler 가 a2a_context UUID 로 lookup
    message_id: str                                  # A2A wire messageId
    task_id: str | None = None                       # Task.history 면 채움
    role: Literal["user", "agent", "system"]
    sender: str
    parts: list[dict[str, Any]] | dict[str, Any]
    prev_message_id: UUID | None = None              # 같은 chronicler 처리 안에서 chain
    metadata: dict[str, Any] = Field(default_factory=dict)


class A2ATaskCreateEvent(_EventBase):
    """A2A Task 생성 — stateful 작업 응답으로 Task wrap 시점."""

    event_type: Literal["a2a.task.create"] = "a2a.task.create"
    context_id: str                                  # A2A wire contextId (lookup)
    task_id: str                                     # A2A wire taskId
    state: Literal[
        "SUBMITTED", "WORKING", "COMPLETED", "INPUT_REQUIRED", "FAILED",
    ] = "SUBMITTED"
    assignment_id: UUID | None = None                # 어느 도메인 assignment 진행
    metadata: dict[str, Any] = Field(default_factory=dict)


class A2ATaskStatusUpdateEvent(_EventBase):
    """Task state transition."""

    event_type: Literal["a2a.task.status_update"] = "a2a.task.status_update"
    task_id: str                                     # A2A wire taskId (lookup)
    state: Literal[
        "SUBMITTED", "WORKING", "COMPLETED", "INPUT_REQUIRED", "FAILED",
    ]
    reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class A2ATaskArtifactEvent(_EventBase):
    """Task 산출물."""

    event_type: Literal["a2a.task.artifact"] = "a2a.task.artifact"
    task_id: str                                     # A2A wire taskId (lookup)
    artifact_id: str                                 # A2A wire artifactId
    name: str | None = None
    parts: list[dict[str, Any]] | dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)


class A2AContextEndEvent(_EventBase):
    """A2A 호출 / 트리 종료 — 정상 / cancel / 에러."""

    event_type: Literal["a2a.context.end"] = "a2a.context.end"
    context_id: str                                  # A2A wire contextId (lookup)
    reason: str = "completed"                        # 'completed' | 'client_disconnect' | 'graph_error' | ...
    duration_ms: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# discriminated union — consumer 가 event_type 으로 분기
A2AEvent = (
    ChatSessionStartEvent
    | ChatAppendEvent
    | ChatSessionEndEvent
    | AssignmentCreateEvent
    | AssignmentUpdateEvent
    | A2AContextStartEvent
    | A2AMessageAppendEvent
    | A2ATaskCreateEvent
    | A2ATaskStatusUpdateEvent
    | A2ATaskArtifactEvent
    | A2AContextEndEvent
)


__all__ = [
    "A2AContextEndEvent",
    "A2AContextStartEvent",
    "A2AEvent",
    "A2AMessageAppendEvent",
    "A2ATaskArtifactEvent",
    "A2ATaskCreateEvent",
    "A2ATaskStatusUpdateEvent",
    "AssignmentCreateEvent",
    "AssignmentUpdateEvent",
    "ChatAppendEvent",
    "ChatSessionEndEvent",
    "ChatSessionStartEvent",
    "EventType",
]
