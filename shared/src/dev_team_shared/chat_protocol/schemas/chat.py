"""Chat send — 사용자 발화 제출 schemas.

`POST /api/chat` body / response. 실제 응답 chunks 는 SSE 채널 (`GET
/api/stream`) 로 별도 흐름.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ChatSendRequest(BaseModel):
    """`POST /api/chat` body — 사용자 발화 제출.

    `session_id` 는 사전에 `POST /api/sessions` 로 생성한 것.
    `prev_chat_id` 는 FE 가 추적한 이전 chat (마지막 agent 응답) 의 chat_id.
    chats 의 chain 결정성 보장 (#75 PR 4). 첫 발화는 None.
    """

    model_config = ConfigDict(extra="forbid")

    session_id: UUID
    text: str
    prev_chat_id: UUID | None = None


class ChatSendResponse(BaseModel):
    """`POST /chat/send` 응답 — 즉시 202 ack. 실제 응답은 SSE 채널로.

    chat_id 등 식별자는 caller (UG) 가 발급해 들고 있음 — 응답엔 status 만.
    """

    model_config = ConfigDict(extra="forbid")

    status: Literal["queued", "processing"] = "processing"


__all__ = [
    "ChatSendRequest",
    "ChatSendResponse",
]
