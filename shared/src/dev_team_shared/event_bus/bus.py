"""EventBus ABC + ValkeyEventBus 구현.

publisher 가 fire-and-forget 으로 publish. 실패해도 본 흐름 (A2A 응답) 차단 X —
로그 + 로컬 retry queue (bounded). retry queue 가 가득 차면 oldest 폐기 (메모리
보호 우선).
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from collections import deque

import redis.asyncio as redis

from dev_team_shared.event_bus.events import A2AEvent

logger = logging.getLogger(__name__)


# Valkey Stream 이름 — 모든 A2A 이벤트가 본 stream 으로 들어감.
# Consumer (CHR) 가 본 이름으로 XREADGROUP.
A2A_EVENTS_STREAM = "a2a-events"


class EventBus(ABC):
    """publish 측 계약. 백엔드 무관.

    구현체는 fire-and-forget 의도 — 실패가 발신자 흐름을 막지 않아야 함.
    실패 시 로깅 / 로컬 buffer / 등으로 흡수.
    """

    @abstractmethod
    async def publish(self, event: A2AEvent) -> None:
        """이벤트 1건 publish."""

    @abstractmethod
    async def aclose(self) -> None:
        """자원 정리. lifespan 종료 시 호출."""


class ValkeyEventBus(EventBus):
    """Valkey Streams (XADD) 기반.

    이벤트는 stream `a2a-events` 의 entry 로 저장. CHR 가 consumer group
    `chronicler` 로 XREADGROUP.

    실패 시: log + 로컬 retry queue (deque, max 1000). 다음 publish 시 retry queue
    먼저 flush. 큐가 차면 oldest 폐기 — 메모리 보호 우선 (관측성보다).
    """

    def __init__(self, client: redis.Redis, *, retry_buffer_max: int = 1000) -> None:
        self._client = client
        self._retry: deque[A2AEvent] = deque(maxlen=retry_buffer_max)
        self._lock = asyncio.Lock()

    @classmethod
    async def create(cls, url: str, *, retry_buffer_max: int = 1000) -> ValkeyEventBus:
        """팩토리 — URL 로 클라이언트 만들고 인스턴스화."""
        client = redis.from_url(url, decode_responses=False)
        # ping 으로 즉시 검증 (실패 시 lifespan 단계에서 잡히는 편이 나음)
        await client.ping()
        return cls(client, retry_buffer_max=retry_buffer_max)

    async def publish(self, event: A2AEvent) -> None:
        async with self._lock:
            # 1) retry queue 먼저 flush (best effort)
            await self._flush_retry_locked()
            # 2) 이번 이벤트 publish
            try:
                await self._xadd_locked(event)
            except Exception:
                logger.exception(
                    "event_bus.publish failed (event_id=%s) — buffering",
                    event.event_id,
                )
                self._retry.append(event)

    async def _flush_retry_locked(self) -> None:
        while self._retry:
            ev = self._retry[0]
            try:
                await self._xadd_locked(ev)
                self._retry.popleft()
            except Exception:
                # 여전히 실패 — flush 중단, 나중에 재시도
                logger.warning(
                    "event_bus.retry still failing (event_id=%s) — keeping in buffer",
                    ev.event_id,
                )
                break

    async def _xadd_locked(self, event: A2AEvent) -> None:
        """Valkey XADD 호출. fields = `payload` (JSON) + `event_type` (filter 용)."""
        payload = event.model_dump_json()
        await self._client.xadd(
            A2A_EVENTS_STREAM,
            {
                b"event_type": event.event_type.encode("utf-8"),
                b"payload": payload.encode("utf-8"),
            },
        )

    async def aclose(self) -> None:
        try:
            await self._client.aclose()
        except Exception:
            logger.exception("event_bus close failed")


__all__ = ["A2A_EVENTS_STREAM", "EventBus", "ValkeyEventBus"]
