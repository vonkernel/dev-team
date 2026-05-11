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


__all__ = [
    "ChatSendRequest",
    "ChatSendResponse",
]
