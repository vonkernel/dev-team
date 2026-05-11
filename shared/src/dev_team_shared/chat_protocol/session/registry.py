"""SessionRegistry — in-memory session_id → SessionRuntime 매핑 + TTL sweeper.

Primary / Architect 의 app.state 에 1개 보관 — 같은 인스턴스를 chat handler
(router / worker) 가 공유.

Lifecycle:
- `start_sweeper()` — lifespan startup 시 1회 호출 (background sweeper task 기동)
- `aclose()` — lifespan shutdown 시 호출 (sweeper cancel + 모든 runtime 정리)
"""

from __future__ import annotations

import asyncio
import logging
import time
from uuid import UUID

import anyio

from dev_team_shared.chat_protocol.session.runtime import (
    DEFAULT_MAX_BACKLOG_MESSAGES,
    SessionRuntime,
)

logger = logging.getLogger(__name__)

DEFAULT_IDLE_TTL_S = 1800.0
DEFAULT_SWEEP_INTERVAL_S = 60.0


class SessionRegistry:
    """in-memory session_id → SessionRuntime 매핑 + TTL sweeper."""

    def __init__(
        self,
        *,
        max_messages: int = DEFAULT_MAX_BACKLOG_MESSAGES,
        idle_ttl_s: float = DEFAULT_IDLE_TTL_S,
        sweep_interval_s: float = DEFAULT_SWEEP_INTERVAL_S,
    ) -> None:
        self._max_messages = max_messages
        self._idle_ttl_s = idle_ttl_s
        self._sweep_interval_s = sweep_interval_s
        self._sessions: dict[UUID, SessionRuntime] = {}
        self._registry_lock = anyio.Lock()
        self._sweeper_task: asyncio.Task | None = None
        self._closed = False

    # ─── lifecycle ──────────────────────────────────────────────────────────

    def start_sweeper(self) -> None:
        """TTL sweeper background task 기동 (lifespan startup 에서 1회)."""
        if self._sweeper_task is not None:
            return
        self._sweeper_task = asyncio.create_task(
            self._sweep_loop(), name="chat-session-sweeper",
        )

    async def aclose(self) -> None:
        """lifespan shutdown — sweeper cancel + 모든 runtime aclose."""
        self._closed = True
        if self._sweeper_task is not None and not self._sweeper_task.done():
            self._sweeper_task.cancel()
            try:
                await self._sweeper_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        async with self._registry_lock:
            runtimes = list(self._sessions.values())
            self._sessions.clear()
        for rt in runtimes:
            try:
                await rt.aclose()
            except Exception:
                logger.exception(
                    "runtime close failed (session_id=%s)", rt.session_id,
                )

    # ─── lookup / mutate ───────────────────────────────────────────────────

    async def get_or_create(self, session_id: UUID) -> SessionRuntime:
        """미등록 session_id 면 lazy create."""
        async with self._registry_lock:
            rt = self._sessions.get(session_id)
            if rt is not None:
                return rt
            rt = SessionRuntime(
                session_id=session_id, max_messages=self._max_messages,
            )
            self._sessions[session_id] = rt
            logger.info("chat session runtime created session_id=%s", session_id)
            return rt

    async def evict(self, session_id: UUID) -> None:
        """특정 session evict (registry 제거 + runtime aclose)."""
        async with self._registry_lock:
            rt = self._sessions.pop(session_id, None)
        if rt is not None:
            await rt.aclose()
            logger.info("chat session runtime evicted session_id=%s", session_id)

    # ─── TTL sweeper ───────────────────────────────────────────────────────

    async def _sweep_loop(self) -> None:
        """주기적으로 idle session evict. sweep_interval_s 마다 1회."""
        while not self._closed:
            try:
                await asyncio.sleep(self._sweep_interval_s)
                await self._sweep_once()
            except asyncio.CancelledError:
                return
            except Exception:
                logger.exception("chat session sweeper iter failed")

    async def _sweep_once(self) -> None:
        """현재 시점 기준 idle TTL 초과 session 들 evict."""
        now = time.monotonic()
        async with self._registry_lock:
            to_evict = [
                sid for sid, rt in self._sessions.items()
                if now - rt.last_activity_at > self._idle_ttl_s
            ]
        for sid in to_evict:
            await self.evict(sid)


__all__ = [
    "DEFAULT_IDLE_TTL_S",
    "DEFAULT_SWEEP_INTERVAL_S",
    "SessionRegistry",
]
