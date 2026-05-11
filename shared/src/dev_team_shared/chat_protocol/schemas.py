"""Chat protocol wire schemas — REST request/response + SSE events.

#75 PR 4. UG↔P/A 사이 통신의 Pydantic 모델 정의. UG / agent / FE 모두 공유
(in-process Pattern B — shared/CLAUDE.md §1).

SSE 이벤트 타입은 `ChatEventType` enum + `ChatEvent` discriminated union.
직렬화는 `sse.py` 의 helper.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ─────────────────────────────────────────────────────────────────────────────
# Session — chat 대화창 단위
# ─────────────────────────────────────────────────────────────────────────────


class SessionCreateRequest(BaseModel):
    """`POST /api/sessions` body — 사용자가 새 chat 시작.

    `agent_endpoint` 는 사용자가 어느 agent 와 대화할지 선택 (Primary / Architect).
    M3 엔 primary 만 지원, M4+ architect 추가.
    """

    model_config = ConfigDict(extra="forbid")

    agent_endpoint: Literal["primary", "architect"] = "primary"
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionRead(BaseModel):
    """session 조회 결과 — `POST /api/sessions` 응답 + `GET /api/sessions[/X]`."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_endpoint: str
    initiator: str
    counterpart: str
    metadata: dict[str, Any]
    started_at: datetime


class SessionUpdateRequest(BaseModel):
    """`PATCH /api/sessions/{id}` body — metadata 일부 갱신.

    표준 키 (`title` / `pinned` / `last_chat_at` / `unread_count`) 또는 비표준
    키 자유 (JSONB). server 가 받은 dict 를 sessions.metadata 에 merge.
    """

    model_config = ConfigDict(extra="forbid")

    metadata: dict[str, Any]


# ─────────────────────────────────────────────────────────────────────────────
# Chat send — 사용자 발화 제출
# ─────────────────────────────────────────────────────────────────────────────


class ChatSendRequest(BaseModel):
    """`POST /api/chat` body — 사용자 발화 제출.

    `session_id` 는 사전에 `POST /api/sessions` 로 생성한 것. `message_id` 는
    FE 가 발급해 dedup key 로 사용.
    """

    model_config = ConfigDict(extra="forbid")

    session_id: UUID
    text: str
    message_id: str | None = None


class ChatSendResponse(BaseModel):
    """`POST /api/chat` 응답 — 즉시 202 ack. 실제 응답은 SSE 채널로."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["queued", "processing"] = "processing"
    message_id: str


# ─────────────────────────────────────────────────────────────────────────────
# SSE events — `GET /api/stream` / agent `GET /chat/stream` 의 이벤트 페이로드
# ─────────────────────────────────────────────────────────────────────────────


class ChatEventType(StrEnum):
    """chat tier SSE 이벤트 타입.

    - `meta`: session 메타 갱신 (예: 새 session_id 알림 — page reload 시)
    - `queued`: 사용자 발화가 큐 적재됨 (agent busy 시)
    - `chunk`: agent 응답 텍스트 chunk (streaming)
    - `message`: 완성된 chat (chunk 끝나면 한 번. message_id 포함)
    - `done`: 한 turn 완료
    - `error`: 에러
    """

    META = "meta"
    QUEUED = "queued"
    CHUNK = "chunk"
    MESSAGE = "message"
    DONE = "done"
    ERROR = "error"


class ChatEvent(BaseModel):
    """SSE 채널의 한 이벤트.

    `payload` 는 type 마다 자유 (Pydantic discriminated union 안 함 — JSONB
    free-form 처럼 type 별 키 변동). 표준 키 가이드:

    | type    | payload 키                                 |
    |---------|---------------------------------------------|
    | meta    | `session_id`, `agent_endpoint`              |
    | queued  | `message_id`, `queue_depth`                 |
    | chunk   | `text`, `message_id`                        |
    | message | `message_id`, `role`, `text`, `created_at`  |
    | done    | (없음)                                       |
    | error   | `message`, `detail` (선택)                   |
    """

    model_config = ConfigDict(extra="forbid")

    type: ChatEventType
    payload: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "ChatEvent",
    "ChatEventType",
    "ChatSendRequest",
    "ChatSendResponse",
    "SessionCreateRequest",
    "SessionRead",
    "SessionUpdateRequest",
]
