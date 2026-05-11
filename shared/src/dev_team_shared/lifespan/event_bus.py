"""EventBus (Valkey) lifespan helper — 필수 인프라.

`VALKEY_URL` env 미설정 / 초기화 실패 시 **기동 종료** (fail-fast). chat tier
+ A2A tier 의 모든 publish 가 이벤트 버스 의존이라 graceful fallback 불가능.

Runtime 의 publish 실패 (Valkey 일시 장애 등) 는 별 layer — publish helper
들이 try/except + 로그로 fire-and-forget (chat 흐름 차단 X).
"""

from __future__ import annotations

import logging
from contextlib import AsyncExitStack

from dev_team_shared.event_bus import ValkeyEventBus

logger = logging.getLogger(__name__)


async def build_event_bus(
    valkey_url: str | None, stack: AsyncExitStack,
) -> ValkeyEventBus:
    """Valkey EventBus 인스턴스화 + cleanup 등록. **fail-fast**.

    Args:
        valkey_url: `VALKEY_URL` env. None / 빈 문자열이면 RuntimeError.
        stack: caller (lifespan) 의 AsyncExitStack — bus.aclose 등록.

    Returns:
        EventBus 인스턴스.

    Raises:
        RuntimeError: `valkey_url` 미설정.
        Exception: `ValkeyEventBus.create` 실패는 그대로 propagate.
    """
    if not valkey_url:
        raise RuntimeError(
            "VALKEY_URL is required — event_bus is a hard dependency for "
            "chat / A2A publish. Set VALKEY_URL env to a reachable Valkey "
            "instance.",
        )
    bus = await ValkeyEventBus.create(valkey_url)
    stack.push_async_callback(bus.aclose)
    logger.info("event_bus ready (Valkey at %s)", valkey_url)
    return bus


__all__ = ["build_event_bus"]
