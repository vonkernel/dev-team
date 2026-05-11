"""Chat tier SSE events — `GET /api/stream` / agent `GET /chat/stream` 의 페이로드.

`ChatEvent` 는 한 SSE `data:` 프레임의 payload. 직렬화 helper 는 `..sse`.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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
]
