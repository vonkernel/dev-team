"""Message-aware ChatEvent 버퍼 — `SessionRuntime` 내부 자료구조.

본 모듈은 `session` 서브패키지의 implementation detail — `session/__init__`
에서 의도적으로 export 하지 않는다 (외부 노출 X). 클래스명에 underscore
prefix 유지로도 internal 의미 표시.

설계:
- 내부 자료구조 = `deque[ChatEvent]`
- send 는 **non-blocking** (sync) — graph 의 forward progress 가 SSE consumer
  상태와 결합되지 않도록.
- backlog (distinct message_id 개수) 가 `max_messages` 초과 시 oldest
  message 의 chunks 통째 drop (atomic). partial message 가 buffer 에 안 남음.
- Message 경계 식별: `ChatEvent.payload["message_id"]`. message_id 없는
  control 이벤트 (meta / done / queued / error) 는 backlog 카운트 제외.
"""

from __future__ import annotations

import logging
from collections import deque

import anyio

from dev_team_shared.chat_protocol.schemas import ChatEvent

logger = logging.getLogger(__name__)


class _ChatEventBuffer:
    """message-aware ChatEvent 버퍼 (SessionRuntime 내부 전용)."""

    def __init__(self, max_messages: int) -> None:
        self._max_messages = max_messages
        self._chunks: deque[ChatEvent] = deque()
        self._not_empty = anyio.Event()
        self._closed = False

    # ─── producer ───────────────────────────────────────────────────────────

    def send(self, ev: ChatEvent) -> None:
        """ChatEvent enqueue — non-blocking. closed 면 silent drop."""
        if self._closed:
            return
        new_id = ev.payload.get("message_id")
        if new_id and self._should_drop_oldest(new_id):
            self._drop_oldest_message()
        self._chunks.append(ev)
        self._not_empty.set()

    # ─── consumer ───────────────────────────────────────────────────────────

    async def receive(self) -> ChatEvent | None:
        """다음 ChatEvent await. closed + buffer 비면 None 반환."""
        while True:
            if self._chunks:
                return self._chunks.popleft()
            if self._closed:
                return None
            self._not_empty = anyio.Event()
            await self._not_empty.wait()

    # ─── lifecycle ──────────────────────────────────────────────────────────

    def close(self) -> None:
        """buffer close — pending receive 들이 None 으로 깨어남."""
        self._closed = True
        self._not_empty.set()

    # ─── internal helpers ──────────────────────────────────────────────────

    def _distinct_message_ids(self) -> list[str]:
        """현재 버퍼에 있는 distinct message_id 들 (등장 순서)."""
        seen: dict[str, None] = {}
        for ev in self._chunks:
            mid = ev.payload.get("message_id")
            if mid and mid not in seen:
                seen[mid] = None
        return list(seen)

    def _should_drop_oldest(self, new_id: str) -> bool:
        """새 message_id 가 enqueue 되려는데 backlog 한도 도달했나?"""
        ids = self._distinct_message_ids()
        if new_id in ids:
            return False
        return len(ids) >= self._max_messages

    def _drop_oldest_message(self) -> None:
        """가장 오래된 message 의 모든 chunks 를 atomic 하게 pop."""
        ids = self._distinct_message_ids()
        if not ids:
            return
        oldest = ids[0]
        new_chunks: deque[ChatEvent] = deque()
        dropped = 0
        for ev in self._chunks:
            if ev.payload.get("message_id") == oldest:
                dropped += 1
                continue
            new_chunks.append(ev)
        self._chunks = new_chunks
        logger.info(
            "chat buffer dropped oldest message_id=%s (%d events)",
            oldest, dropped,
        )


__all__ = ["_ChatEventBuffer"]
