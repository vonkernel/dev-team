"""LangGraph Postgres checkpointer lifespan helper.

`DATABASE_URI` env 활성이면 `AsyncPostgresSaver` 를 caller 의 AsyncExitStack
에 enter, 미활성이면 None (in-memory checkpointer 폴백 — LangGraph default).
"""

from __future__ import annotations

import logging
from contextlib import AsyncExitStack

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from dev_team_shared.utils import mask_dsn

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


__all__ = ["build_checkpointer"]
