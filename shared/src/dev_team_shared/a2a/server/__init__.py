"""A2A 서버 추상화.

각 에이전트가 공유하는 FastAPI A2A 서버 구성 요소:

- `MethodHandler` — JSON-RPC 메서드 하나를 처리하는 추상 베이스.
- `make_a2a_router` — `/healthz`, `/.well-known/agent-card.json`,
  `/a2a/{assistant_id}` 를 마운트한 APIRouter 팩토리.
- `sse_pack`, `sse_response` — SSE 직렬화 / StreamingResponse 헬퍼.
- `graph_handlers` — LangGraph 기반 에이전트를 위한 기본 메서드 핸들러
  (SendMessage, SendStreamingMessage).
"""

from dev_team_shared.a2a.server.handler import MethodHandler
from dev_team_shared.a2a.server.router import make_a2a_router
from dev_team_shared.a2a.server.sse import (
    KEEPALIVE_SENTINEL,
    aiter_with_keepalive,
    sse_pack,
    sse_response,
)

__all__ = [
    "KEEPALIVE_SENTINEL",
    "MethodHandler",
    "aiter_with_keepalive",
    "make_a2a_router",
    "sse_pack",
    "sse_response",
]
