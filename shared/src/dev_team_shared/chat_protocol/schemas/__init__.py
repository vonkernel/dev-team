"""Chat protocol wire schemas — REST request/response + SSE events.

#75 PR 4. UG↔P/A 사이 통신의 Pydantic 모델. 도메인별 파일 분리:

- `session` — chat 대화창 lifecycle (SessionCreateRequest / SessionRead /
  SessionUpdateRequest)
- `chat` — 발화 제출 (ChatSendRequest / ChatSendResponse)
- `events` — SSE 채널의 한 이벤트 (ChatEvent / ChatEventType)

본 `__init__` 는 re-export 만 — caller 는 `from dev_team_shared.chat_protocol
import ChatEvent` 처럼 평탄하게 import 가능.
"""

from dev_team_shared.chat_protocol.schemas.chat import (
    ChatSendRequest,
    ChatSendResponse,
)
from dev_team_shared.chat_protocol.schemas.events import (
    ChatEvent,
    ChatEventType,
)
from dev_team_shared.chat_protocol.schemas.session import (
    SessionCreateRequest,
    SessionRead,
    SessionUpdateRequest,
)

__all__ = [
    "ChatEvent",
    "ChatEventType",
    "ChatSendRequest",
    "ChatSendResponse",
    "SessionCreateRequest",
    "SessionRead",
    "SessionUpdateRequest",
]
