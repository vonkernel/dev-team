"""Chat session runtime (P/A 공통) — message-aware in-memory buffer + TTL eviction.

UG↔P/A chat tier 의 server 측 (Primary / Architect) 공통 인프라.

설계 핵심:
- **send 가 절대 block X**: graph 의 forward progress 를 SSE consumer 상태와
  결합하지 않음. consumer 끊긴 채 producer 가 chunks 흘려도 graph 진행 보장 →
  LLM call 노드 종료 → AIMessage state append → checkpoint snapshot ✓
- **Drop 단위 = message**: backlog 한도 초과 시 oldest message 의 chunks 통째
  drop (atomic). partial message 가 buffer 에 남지 않음.
- **TTL evict 단위 = message**: `last_activity_at` 을 매 send 시 갱신 →
  message 흐르는 동안 idle timer reset → 진행 중 evict X.

policy:
- `MAX_BACKLOG_MESSAGES` (기본 5): consumer 끊긴 채 보관할 max message 개수
- `IDLE_TTL_S` (기본 1800 = 30분): 마지막 활동 이후 idle → evict
- `SWEEP_INTERVAL_S` (기본 60): sweeper background task 주기

알려진 한계:
- TTL evict 가 진행 중 task 도 cancel — 그 시점까지의 graph state 는
  LangGraph checkpoint 에 보존되므로 다음 POST 가 이어 받을 수 있음.
- 단일 process in-memory — 다중 instance scale-out 불가 (M3 scope 가정).
"""

from __future__ import annotations

import asyncio
import logging
import time
from uuid import UUID

import anyio

from dev_team_shared.chat_protocol._chat_event_buffer import _ChatEventBuffer
from dev_team_shared.chat_protocol.schemas import ChatEvent

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# 기본 정책 상수 (SessionRegistry 가 override)
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_MAX_BACKLOG_MESSAGES = 5
DEFAULT_IDLE_TTL_S = 1800.0
DEFAULT_SWEEP_INTERVAL_S = 60.0


# ─────────────────────────────────────────────────────────────────────────────
# SessionRuntime — 한 session 의 runtime 상태
# ─────────────────────────────────────────────────────────────────────────────


class SessionRuntime:
    """한 chat session 의 runtime 상태 (P/A 공통).

    필드:
    - `session_id` — chat session UUID
    - `_buffer` — message-aware ChatEventBuffer (캡슐화, 외부 직접 접근 X)
    - `lock` — 같은 session 의 graph 호출 sequential 보장
    - `last_activity_at` — TTL 판정. 매 send 시 갱신.
    - `_task` — 진행 중 background task ref (evict 시 cancel)
    """

    def __init__(
        self,
        session_id: UUID,
        max_messages: int = DEFAULT_MAX_BACKLOG_MESSAGES,
    ) -> None:
        self.session_id = session_id
        self._buffer = _ChatEventBuffer(max_messages=max_messages)
        self.lock = anyio.Lock()
        self.last_activity_at: float = time.monotonic()
        self._task: asyncio.Task | None = None

    # ─── producer / consumer API ────────────────────────────────────────────

    def send(self, ev: ChatEvent) -> None:
        """ChatEvent enqueue (non-blocking) + activity 시각 갱신."""
        self._buffer.send(ev)
        self.last_activity_at = time.monotonic()

    async def receive(self) -> ChatEvent | None:
        """다음 ChatEvent await. runtime closed 면 None."""
        return await self._buffer.receive()

    # ─── lifecycle ──────────────────────────────────────────────────────────

    def attach_task(self, task: asyncio.Task) -> None:
        """진행 중 background task ref 보관 (evict 시 cancel 용)."""
        self._task = task

    async def aclose(self) -> None:
        """runtime 정리 — task cancel (있으면) + buffer close.

        TTL evict / lifespan shutdown 시 호출. 진행 중 graph task 가 있으면
        cancel — graph 의 마지막 완료 노드까지의 state 는 LangGraph
        checkpoint 에 보존되므로 손실 X (다음 POST 가 이어 받음).
        """
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        self._buffer.close()


# ─────────────────────────────────────────────────────────────────────────────
# SessionRegistry — in-memory dict + TTL sweeper
# ─────────────────────────────────────────────────────────────────────────────


class SessionRegistry:
    """in-memory session_id → SessionRuntime 매핑 + TTL sweeper.

    Primary / Architect 의 app.state 에 1개 보관 — 같은 인스턴스를 chat
    handler (router / worker) 가 공유.

    Lifecycle:
    - `start_sweeper()` — lifespan startup 시 1회 호출 (background sweeper task 기동)
    - `aclose()` — lifespan shutdown 시 호출 (sweeper cancel + 모든 runtime 정리)
    """

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
    "DEFAULT_MAX_BACKLOG_MESSAGES",
    "DEFAULT_SWEEP_INTERVAL_S",
    "SessionRegistry",
    "SessionRuntime",
]
