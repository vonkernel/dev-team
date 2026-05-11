"""Primary 의 chat protocol handler — `POST /chat/send` + `GET /chat/stream`.

#75 PR 4 commit 6. UG↔P chat tier 통신의 server 측. wire schemas / SSE
serialization 은 `dev_team_shared.chat_protocol` 사용.

Lazy session: 미등록 session_id 가 도착하면 그 시점에 `SessionRuntime` 등록.
UG 가 사전에 `POST /api/sessions` 로 session row 를 만들지만 Primary 는
그 fact 를 모르고 lazy 생성 — LangGraph thread_id (= session_id) 만 매핑하면
충분 (graph 의 checkpointer 가 thread 별 history 관리).

Concurrency 모델 (per session):
- `outgoing_*` MemoryObjectStream 한 쌍 — POST 가 send, GET 이 receive.
- `lock` — 한 session 에 한 번에 graph 호출 1개 (sequential). 두 번째 POST 는
  lock 대기 → 큐 효과.

Subscriber 1 명 가정 (FE 한 탭). 다중 subscriber (multi-tab) 필요해지면
broadcast 패턴 도입 (v2).
"""

from __future__ import annotations

import logging
import math
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import anyio
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from dev_team_shared.a2a.server.graph_handlers.parse import stringify_ai_content
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
from langchain_core.messages import AIMessage, HumanMessage

logger = logging.getLogger(__name__)

# SSE keepalive 주기 (초). proxy idle timeout 방어용.
_KEEPALIVE_S = 15.0
# Graph total timeout — A2A handler 의 AGENT_TOTAL_TIMEOUT_S 와 일관.
_GRAPH_TIMEOUT_S = 180.0


@dataclass
class SessionRuntime:
    """한 session 의 runtime 상태.

    `outgoing_send` / `outgoing_receive` 는 짝. POST 처리 background task 가
    chunks / events 를 send, GET /chat/stream 이 receive.
    `lock` 은 graph 호출 sequential 보장 — 두 번째 POST 는 첫 처리 끝날 때까지 대기.
    """

    session_id: UUID
    outgoing_send: MemoryObjectSendStream[ChatEvent]
    outgoing_receive: MemoryObjectReceiveStream[ChatEvent]
    lock: anyio.Lock = field(default_factory=anyio.Lock)


class SessionRegistry:
    """in-memory session_id → SessionRuntime 매핑.

    Primary 의 app.state 에 1개 보관. lifespan 종료 시 모든 stream close.
    """

    def __init__(self) -> None:
        self._sessions: dict[UUID, SessionRuntime] = {}
        self._registry_lock = anyio.Lock()

    async def get_or_create(self, session_id: UUID) -> SessionRuntime:
        """미등록 시 lazy create (lock 으로 race 보호)."""
        async with self._registry_lock:
            rt = self._sessions.get(session_id)
            if rt is not None:
                return rt
            send, receive = anyio.create_memory_object_stream[ChatEvent](
                max_buffer_size=math.inf,
            )
            rt = SessionRuntime(
                session_id=session_id,
                outgoing_send=send,
                outgoing_receive=receive,
            )
            self._sessions[session_id] = rt
            logger.info("chat session runtime created session_id=%s", session_id)
            return rt

    async def aclose(self) -> None:
        """모든 session 의 stream close (lifespan shutdown 시 호출)."""
        for rt in self._sessions.values():
            try:
                await rt.outgoing_send.aclose()
            except Exception:
                logger.exception(
                    "outgoing_send close failed (session_id=%s)", rt.session_id,
                )
            try:
                await rt.outgoing_receive.aclose()
            except Exception:
                logger.exception(
                    "outgoing_receive close failed (session_id=%s)", rt.session_id,
                )
        self._sessions.clear()


# ─────────────────────────────────────────────────────────────────────────────
# Router
# ─────────────────────────────────────────────────────────────────────────────


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

        # background task — 별 lifespan 스코프에서 graph 호출 + chunks push.
        # anyio task group 을 app.state 에 두고 spawn. 또는 asyncio 의
        # create_task 로 fire-and-forget. 후자 더 단순.
        import asyncio

        asyncio.create_task(
            _run_graph_and_stream(runtime, request, body.text, message_id),
            name=f"chat_send-{body.session_id}",
        )
        return ChatSendResponse(status="processing", message_id=message_id)

    @router.get("/chat/stream")
    async def chat_stream(session_id: UUID, request: Request) -> StreamingResponse:
        """영속 SSE per session — 같은 session 의 모든 응답 / event 받음."""
        registry: SessionRegistry = request.app.state.chat_session_registry
        runtime = await registry.get_or_create(session_id)

        async def event_iter() -> AsyncIterator[str]:
            # 첫 meta 이벤트 (session_id 알림, FE 가 컨텍스트 확인용)
            yield chat_event_sse_line(ChatEvent(
                type=ChatEventType.META,
                payload={"session_id": str(session_id)},
            ))
            try:
                async for ev in _aiter_with_keepalive(
                    runtime.outgoing_receive, _KEEPALIVE_S,
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
# Internal — background graph 호출 + chunks push
# ─────────────────────────────────────────────────────────────────────────────


async def _run_graph_and_stream(
    runtime: SessionRuntime,
    request: Request,
    text: str,
    message_id: str,
) -> None:
    """graph 호출 → chunks 를 runtime.outgoing_send 로 push.

    lock 으로 sequential — 같은 session 의 두 번째 POST 는 첫 처리 끝날 때까지 대기.
    실패는 SSE 에 `error` 이벤트로 통보.
    """
    graph = request.app.state.graph
    async with runtime.lock:
        try:
            with anyio.fail_after(_GRAPH_TIMEOUT_S):
                # session_id 가 LangGraph thread_id — 같은 session 으로 N turn
                # 호출 시 graph 의 체크포인터가 thread history 누적.
                config = {"configurable": {"thread_id": str(runtime.session_id)}}
                async for msg_chunk, metadata in graph.astream(
                    {"messages": [HumanMessage(content=text)]},
                    config=config,
                    stream_mode="messages",
                ):
                    # classify_response 노드의 token 은 사용자에게 노출 X.
                    if metadata.get("langgraph_node") == "classify_response":
                        continue
                    if not isinstance(msg_chunk, AIMessage):
                        continue
                    text_chunk = stringify_ai_content(msg_chunk.content)
                    if not text_chunk:
                        continue
                    await runtime.outgoing_send.send(ChatEvent(
                        type=ChatEventType.CHUNK,
                        payload={"text": text_chunk, "message_id": message_id},
                    ))
            await runtime.outgoing_send.send(ChatEvent(
                type=ChatEventType.DONE,
                payload={"message_id": message_id},
            ))
        except TimeoutError:
            logger.warning(
                "chat session graph timeout (>%ss) session_id=%s",
                int(_GRAPH_TIMEOUT_S), runtime.session_id,
            )
            await _send_error(runtime, message_id, "graph timeout")
        except Exception as exc:
            logger.exception(
                "chat session graph failed session_id=%s", runtime.session_id,
            )
            await _send_error(runtime, message_id, f"{type(exc).__name__}: {exc}")


async def _send_error(
    runtime: SessionRuntime, message_id: str, detail: str,
) -> None:
    try:
        await runtime.outgoing_send.send(ChatEvent(
            type=ChatEventType.ERROR,
            payload={"message_id": message_id, "message": detail},
        ))
    except Exception:
        logger.exception("error event send failed (session_id=%s)", runtime.session_id)


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


__all__ = [
    "SessionRegistry",
    "SessionRuntime",
    "make_chat_router",
]
