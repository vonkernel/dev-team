"""HTTP 엔드포인트 — 책임별 sub-router 분리 후 통합 `router` 노출.

각 sub-router 의 책임:
- `health`: healthz + Primary AgentCard 프록시
- `chat`: 사용자 발화 제출 (`POST /api/chat`) + 영속 SSE forward (`GET /api/stream`)
- `sessions`: session lifecycle / metadata — `POST` / `GET list` / `PATCH`
- `history`: chat history read (`GET /api/history`)

라우트 핸들러는 **어떤 자원이 필요한지** 만 선언하고 실제 I/O 는
upstream / doc_store / event_bus 같은 주입된 어댑터에 위임 (DIP).
"""

from fastapi import APIRouter

from user_gateway.routes.chat import ChatRequest
from user_gateway.routes.chat import router as chat_router
from user_gateway.routes.health import router as health_router
from user_gateway.routes.history import router as history_router
from user_gateway.routes.sessions import router as sessions_router

router = APIRouter()
router.include_router(health_router)
router.include_router(sessions_router)
router.include_router(chat_router)
router.include_router(history_router)


__all__ = ["ChatRequest", "router"]
