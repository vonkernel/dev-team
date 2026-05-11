"""Chat protocol (사용자 ↔ Primary / Architect 통신) — wire 정의.

UG↔P/A 의 chat tier 통신 (#75). REST POST + 영속 SSE per session 패턴
([architecture-chat-protocol](../../../../../docs/proposal/architecture-chat-protocol.md)).

Pattern B (in-process library) — agent 의 chat handler / UG 의 client / FE
시뮬레이션 모두 이 schemas / SSE helper 를 공유.

핵심:
- `Schemas`: SessionCreate, SessionRead, ChatSend, ChatStream events
- `SSE serialization`: chat tier SSE 이벤트 → `data: {json}\n\n`

agent 측 endpoint:
- `POST /chat/send`  — chat 발화 제출
- `GET /chat/stream?session_id=X` — 영속 SSE per session
- (lazy) session 인지 — 미등록 session_id 받으면 graph thread 새로 만듦
"""

from dev_team_shared.chat_protocol.schemas import (
    ChatEvent,
    ChatEventType,
    ChatSendRequest,
    ChatSendResponse,
    SessionCreateRequest,
    SessionRead,
    SessionUpdateRequest,
)
from dev_team_shared.chat_protocol.session_runtime import (
    DEFAULT_IDLE_TTL_S,
    DEFAULT_MAX_BACKLOG_MESSAGES,
    DEFAULT_SWEEP_INTERVAL_S,
    SessionRegistry,
    SessionRuntime,
)
from dev_team_shared.chat_protocol.sse import (
    chat_event_sse_line,
    keepalive_sse_line,
)

__all__ = [
    "DEFAULT_IDLE_TTL_S",
    "DEFAULT_MAX_BACKLOG_MESSAGES",
    "DEFAULT_SWEEP_INTERVAL_S",
    "ChatEvent",
    "ChatEventType",
    "ChatSendRequest",
    "ChatSendResponse",
    "SessionCreateRequest",
    "SessionRead",
    "SessionRegistry",
    "SessionRuntime",
    "SessionUpdateRequest",
    "chat_event_sse_line",
    "keepalive_sse_line",
]
