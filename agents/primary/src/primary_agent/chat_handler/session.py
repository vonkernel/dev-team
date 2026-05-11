"""Chat session 의 runtime 상태 + in-memory registry.

`SessionRuntime`: 한 session 의 wire-level 상태 (anyio MemoryObjectStream
한 쌍 + graph 호출 sequential 보장 lock).

`SessionRegistry`: session_id → runtime 매핑. 미등록 시 lazy create.
Primary 의 lifespan 동안 1 인스턴스 (`app.state.chat_session_registry`).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from uuid import UUID

import anyio
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from dev_team_shared.chat_protocol import ChatEvent

logger = logging.getLogger(__name__)


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


__all__ = [
    "SessionRegistry",
    "SessionRuntime",
]
