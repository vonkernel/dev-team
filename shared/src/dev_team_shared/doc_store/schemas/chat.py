"""chats Pydantic 모델 — session 안의 한 발화 (chat tier).

chats 는 immutable — update 미노출. session 안의 시간순 흐름은 prev_chat_id
chain 으로 추적.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ChatRole = Literal["user", "agent", "system"]


class ChatCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID                                         # publisher-supplied (#75 PR 4)
    session_id: UUID
    prev_chat_id: UUID | None = None
    role: ChatRole
    sender: str                                      # 'user' / 'primary' / ...
    content: list[dict[str, Any]] | dict[str, Any]   # A2A parts 형태
    message_id: str | None = None                    # FE 또는 server 발급 (wire-level)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    prev_chat_id: UUID | None
    role: ChatRole
    sender: str
    content: list[dict[str, Any]] | dict[str, Any]
    message_id: str | None
    metadata: dict[str, Any]
    created_at: datetime
