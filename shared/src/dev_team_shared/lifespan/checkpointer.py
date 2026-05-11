"""LangGraph Postgres checkpointer lifespan helper + DSN 마스킹.

`DATABASE_URI` env 활성이면 `AsyncPostgresSaver` 를 caller 의 AsyncExitStack
에 enter, 미활성이면 None (in-memory checkpointer 폴백 — LangGraph default).
"""

from __future__ import annotations

import logging
from contextlib import AsyncExitStack

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

logger = logging.getLogger(__name__)


async def build_checkpointer(
    database_uri: str | None, stack: AsyncExitStack,
) -> BaseCheckpointSaver | None:
    """DSN 활성이면 AsyncPostgresSaver 를 stack 에 enter, 미활성이면 None.

    None 반환 시 caller 의 graph 가 in-memory state 로 동작 (재시작 시 휘발).

    Args:
        database_uri: Postgres DSN (예: `postgres://user:pass@host:5432/db`).
            None / 빈 문자열이면 in-memory.
        stack: caller (lifespan) 의 AsyncExitStack — checkpointer 의 async
            context 를 enter (lifespan 종료 시 정리).
    """
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
    """비밀번호를 마스킹한 DSN (로그 안전성).

    `postgres://user:secret@host/db` → `postgres://user:***@host/db`.
    `@` 또는 `://` 없으면 원본 그대로 반환.
    """
    if "@" in dsn and "://" in dsn:
        scheme, rest = dsn.split("://", 1)
        creds, host = rest.split("@", 1)
        if ":" in creds:
            user = creds.split(":", 1)[0]
            return f"{scheme}://{user}:***@{host}"
    return dsn


__all__ = ["build_checkpointer", "mask_dsn"]
