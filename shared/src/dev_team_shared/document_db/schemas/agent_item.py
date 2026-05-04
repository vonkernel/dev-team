"""agent_items Pydantic 모델 (immutable, update 없음)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

AgentItemRole = Literal["user", "agent", "system"]


class AgentItemCreate(BaseModel):
    """대화 메시지 1건. 한 번 쓰면 변경 X (audit 성격)."""

    model_config = ConfigDict(extra="forbid")

    agent_session_id: UUID
    prev_item_id: UUID | None = None
    role: AgentItemRole
    sender: str
    content: dict[str, Any] | list[Any]   # A2A Message.parts 그대로
    message_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_session_id: UUID
    prev_item_id: UUID | None
    role: AgentItemRole
    sender: str
    content: Any
    message_id: str | None
    metadata: dict[str, Any]
    created_at: datetime
