"""SessionRuntime — 한 chat session 의 runtime 상태 (P/A 공통).

설계 핵심:
- send 가 **절대 block X**: graph 의 forward progress 가 SSE consumer 상태와
  결합되지 않음. consumer 끊긴 채여도 graph 진행 보장 → LLM call 노드 종료 →
  AIMessage state append → checkpoint snapshot ✓
- Drop 단위 = message: `_ChatEventBuffer` 가 backlog 초과 시 oldest message
  의 chunks 통째 atomic drop.
- TTL evict 단위 = message: `last_activity_at` 을 매 send 시 갱신 → message
  흐르는 동안에는 evict X.
"""

from __future__ import annotations

import asyncio
import logging
import time
from uuid import UUID

import anyio

from dev_team_shared.chat_protocol.schemas import ChatEvent
from dev_team_shared.chat_protocol.session.chat_event_buffer import (
    _ChatEventBuffer,
)

logger = logging.getLogger(__name__)

# SessionRegistry 가 명시적으로 override 가능. 단독 SessionRuntime 생성 시 기본.
DEFAULT_MAX_BACKLOG_MESSAGES = 5


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


__all__ = ["DEFAULT_MAX_BACKLOG_MESSAGES", "SessionRuntime"]
