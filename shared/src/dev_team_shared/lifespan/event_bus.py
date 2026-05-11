"""EventBus (Valkey) lifespan helper — 활성 시 인스턴스화 + cleanup 등록.

`VALKEY_URL` env 미설정 시 None 반환 (publish helper 들이 no-op). 초기화 실패
시에도 graceful fallback — agent 가 publish 안 되더라도 본 흐름 차단 X.
"""

from __future__ import annotations

import logging
from contextlib import AsyncExitStack

from dev_team_shared.event_bus import ValkeyEventBus

logger = logging.getLogger(__name__)


async def build_event_bus(
    valkey_url: str | None, stack: AsyncExitStack,
) -> ValkeyEventBus | None:
    """Valkey 가 활성이면 EventBus 인스턴스화 + cleanup 등록. 실패는 graceful.

    Args:
        valkey_url: `VALKEY_URL` env. None / 빈 문자열이면 publish 비활성.
        stack: caller (lifespan) 의 AsyncExitStack — bus.aclose 등록.

    Returns:
        EventBus 인스턴스 또는 None (미활성 / 실패).
    """
    if not valkey_url:
        logger.info("VALKEY_URL not set — A2A 이벤트 publish 비활성화")
        return None
    try:
        bus = await ValkeyEventBus.create(valkey_url)
    except Exception:
        logger.exception(
            "ValkeyEventBus 초기화 실패 (url=%s) — publish 비활성화로 진행",
            valkey_url,
        )
        return None
    stack.push_async_callback(bus.aclose)
    logger.info("event_bus ready (Valkey at %s)", valkey_url)
    return bus


__all__ = ["build_event_bus"]
