"""A2A 대화 이벤트 Pydantic 스키마.

publisher (UG / 에이전트) 와 consumer (CHR) 가 공유하는 contract.
event_id 는 idempotency key — CHR 의 재시도 시 중복 방지.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

EventType = Literal["session.start", "item.append", "session.end"]


def _utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


class _EventBase(BaseModel):
    """모든 A2A 이벤트의 공통 필드."""

    model_config = ConfigDict(extra="forbid")

    # idempotency — consumer 가 중복 처리 안 하도록
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=_utc_now)

    # session 식별 (모든 이벤트 공통)
    context_id: str
    trace_id: str | None = None

    # 양 당사자
    initiator: str   # 'user' | 'primary' | ...
    counterpart: str

    # agent_task 연결 — publisher 가 알면 채움. 모르면 None → CHR fallback (#34) 으로 임시 task 생성
    agent_task_id: UUID | None = None


class SessionStartEvent(_EventBase):
    """세션 시작 — counterpart 가 incoming A2A 요청 받았을 때."""

    event_type: Literal["session.start"] = "session.start"
    topic: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ItemAppendEvent(_EventBase):
    """메시지 1개 — user / agent 가 보낸 한 발화."""

    event_type: Literal["item.append"] = "item.append"
    role: Literal["user", "agent", "system"]
    sender: str                           # 'user' / 'primary' / ...
    content: dict[str, Any] | list[Any]   # A2A Message.parts 그대로
    message_id: str | None = None         # 원본 A2A messageId (디버그용)
    prev_item_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionEndEvent(_EventBase):
    """세션 종료 — 정상 / 비정상 모두."""

    event_type: Literal["session.end"] = "session.end"
    reason: str = "completed"             # 'completed' | 'client_disconnect' | 'graph_error' | ...
    duration_ms: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# discriminated union — consumer 가 event_type 으로 분기
A2AEvent = SessionStartEvent | ItemAppendEvent | SessionEndEvent


__all__ = [
    "A2AEvent",
    "EventType",
    "ItemAppendEvent",
    "SessionEndEvent",
    "SessionStartEvent",
]
