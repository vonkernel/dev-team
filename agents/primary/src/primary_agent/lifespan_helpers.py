"""Primary lifespan 의 인프라 wiring helper — event_bus / checkpointer / 로깅.

lifespan 본문에서 인프라 디테일을 분리. 각 helper 는 단일 책임:
- `build_event_bus` — Valkey 활성 시 EventBus 인스턴스화
- `build_checkpointer` — DSN 활성 시 AsyncPostgresSaver enter (in-memory fallback)
- `mask_dsn` — 로그 안전성 (비밀번호 마스킹)
- `log_runtime_ready` — 기동 완료 시 카탈로그 한 줄
"""

from __future__ import annotations

import logging
from contextlib import AsyncExitStack

from dev_team_shared.event_bus import ValkeyEventBus
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from primary_agent.channels import Channels

logger = logging.getLogger(__name__)


async def build_event_bus(
    valkey_url: str | None, stack: AsyncExitStack,
) -> ValkeyEventBus | None:
    """Valkey 가 활성이면 EventBus 인스턴스화 + cleanup 등록. 실패는 graceful."""
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


async def build_checkpointer(
    database_uri: str | None, stack: AsyncExitStack,
) -> BaseCheckpointSaver | None:
    """DSN 활성이면 AsyncPostgresSaver 를 stack 에 enter, 미활성이면 None (in-memory)."""
    if not database_uri:
        logger.warning(
            "DATABASE_URI not set — running with in-memory state "
            "(non-durable across restarts)",
        )
        return None
    checkpointer = await stack.enter_async_context(
        AsyncPostgresSaver.from_conn_string(database_uri),
    )
    await checkpointer.setup()  # idempotent
    logger.info("Postgres checkpointer ready (%s)", mask_dsn(database_uri))
    return checkpointer


def mask_dsn(dsn: str) -> str:
    """비밀번호를 마스킹한 DSN (로그 안전성)."""
    if "@" in dsn and "://" in dsn:
        scheme, rest = dsn.split("://", 1)
        creds, host = rest.split("@", 1)
        if ":" in creds:
            user = creds.split(":", 1)[0]
            return f"{scheme}://{user}:***@{host}"
    return dsn


def log_runtime_ready(channels: Channels, tools: list[BaseTool]) -> None:
    """기동 완료 시점의 채널 / tool 카탈로그 한 줄 요약."""
    logger.info(
        "primary tools wired: doc_store=on, issue_tracker=%s, wiki=%s, librarian=%s, total=%d",
        "on" if channels.issue_tracker else "off",
        "on" if channels.wiki else "off",
        "on" if channels.librarian else "off",
        len(tools),
    )


__all__ = [
    "build_checkpointer",
    "build_event_bus",
    "log_runtime_ready",
    "mask_dsn",
]
