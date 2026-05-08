"""a2a_messages Pydantic 모델 — A2A `Message` 객체 영속.

A2A 스펙상 Message 는 두 모드:
- Standalone (taskId 없음) — trivial transaction / pre-commitment negotiation
- Task-bound (taskId 채워짐) — 이미 commit 된 Task 의 history 일원

`a2a_task_id` NULLABLE FK 로 표현.

immutable — update 미노출.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

A2AMessageRole = Literal["user", "agent", "system"]


class A2AMessageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str                                  # A2A wire messageId
    a2a_context_id: UUID
    a2a_task_id: UUID | None = None                  # Task.history 면 채움
    role: A2AMessageRole
    sender: str
    parts: list[dict[str, Any]] | dict[str, Any]
    prev_message_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class A2AMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    message_id: str
    a2a_context_id: UUID
    a2a_task_id: UUID | None
    role: A2AMessageRole
    sender: str
    parts: list[dict[str, Any]] | dict[str, Any]
    prev_message_id: UUID | None
    metadata: dict[str, Any]
    created_at: datetime
