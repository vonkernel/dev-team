"""Chat protocol FastAPI router — `POST /chat/send` + `GET /chat/stream`.

route handler 는 thin — runtime / worker / SSE helper 만 호출:
- POST: SessionRegistry 에서 runtime 가져옴 → background task (worker) spawn
  → 즉시 202 ack
- GET: SessionRegistry 에서 runtime 가져옴 → outgoing_receive 에서 ChatEvent
  를 SSE 라인으로 yield
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from uuid import UUID

import anyio
from anyio.streams.memory import MemoryObjectReceiveStream
from dev_team_shared.chat_protocol import (
    ChatEvent,
    ChatEventType,
    ChatSendRequest,
    ChatSendResponse,
    chat_event_sse_line,
    keepalive_sse_line,
)
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from primary_agent.chat_handler.session import SessionRegistry
from primary_agent.chat_handler.worker import run_session_turn

logger = logging.getLogger(__name__)

# SSE keepalive 주기 (초). proxy idle timeout 방어용.
KEEPALIVE_S = 15.0


def make_chat_router() -> APIRouter:
    """chat protocol handler — `POST /chat/send` + `GET /chat/stream`."""
    router = APIRouter()

    @router.post("/chat/send", response_model=ChatSendResponse)
    async def chat_send(body: ChatSendRequest, request: Request) -> ChatSendResponse:
        """사용자 발화 receive → background graph 호출 → 즉시 202 ack.

        실제 응답은 `GET /chat/stream` 의 SSE 채널로.
        """
        registry: SessionRegistry = request.app.state.chat_session_registry
        runtime = await registry.get_or_create(body.session_id)
        message_id = body.message_id or f"ug-msg-{body.session_id}"
        asyncio.create_task(
            run_session_turn(runtime, request, body.text, message_id),
            name=f"chat_send-{body.session_id}",
        )
        return ChatSendResponse(status="processing", message_id=message_id)

    @router.get("/chat/stream")
    async def chat_stream(session_id: UUID, request: Request) -> StreamingResponse:
        """영속 SSE per session — 같은 session 의 모든 응답 / event 받음."""
        registry: SessionRegistry = request.app.state.chat_session_registry
        runtime = await registry.get_or_create(session_id)

        async def event_iter() -> AsyncIterator[str]:
            # 첫 meta 이벤트 (session_id 알림 — FE 가 컨텍스트 확인용)
            yield chat_event_sse_line(ChatEvent(
                type=ChatEventType.META,
                payload={"session_id": str(session_id)},
            ))
            try:
                async for ev in _aiter_with_keepalive(
                    runtime.outgoing_receive, KEEPALIVE_S,
                ):
                    if ev is None:
                        yield keepalive_sse_line()
                        continue
                    if await _is_disconnected(request):
                        logger.info(
                            "chat_stream client disconnected session_id=%s",
                            session_id,
                        )
                        return
                    yield chat_event_sse_line(ev)
            except anyio.EndOfStream:
                return

        return StreamingResponse(
            event_iter(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    return router


# ─────────────────────────────────────────────────────────────────────────────
# Internal — SSE iter helpers
# ─────────────────────────────────────────────────────────────────────────────


async def _aiter_with_keepalive(
    receive: MemoryObjectReceiveStream[ChatEvent],
    keepalive_s: float,
) -> AsyncIterator[ChatEvent | None]:
    """receive 에서 event 가 idle 하면 `None` (keepalive sentinel) 을 yield.

    `None` 받으면 caller 가 keepalive comment 발송. 진짜 event 받으면 그대로 yield.
    """
    while True:
        try:
            with anyio.fail_after(keepalive_s):
                ev = await receive.receive()
            yield ev
        except TimeoutError:
            yield None
        except anyio.EndOfStream:
            return


async def _is_disconnected(request: Request) -> bool:
    try:
        return await request.is_disconnected()
    except Exception:
        return False


__all__ = ["make_chat_router"]
