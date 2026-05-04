"""FastMCP 싱글턴 + lifespan.

본 모듈이 `mcp` 인스턴스를 노출. tools/ 의 각 모듈이 본 인스턴스를 import 해
`@mcp.tool()` 으로 도구 등록. lifespan 은 Repository 들을 만들어 AppContext 로
yield → 도구는 `ctx.request_context.lifespan_context.X` 로 접근.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from document_db_mcp.config import Settings
from document_db_mcp.db import apply_migrations, pool_lifespan
from document_db_mcp.repositories import (
    AgentItemRepository,
    AgentSessionRepository,
    AgentTaskRepository,
    IssueRepository,
    WikiPageRepository,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AppContext:
    """lifespan 이 yield 하는 의존성 묶음. 도구는 본 객체로부터 repository 를 꺼내 씀."""

    agent_task: AgentTaskRepository
    agent_session: AgentSessionRepository
    agent_item: AgentItemRepository
    issue: IssueRepository
    wiki_page: WikiPageRepository


@asynccontextmanager
async def _app_lifespan(_server: FastMCP) -> AsyncIterator[AppContext]:
    settings = Settings()

    if settings.auto_migrate:
        logger.info("applying migrations…")
        await asyncio.to_thread(apply_migrations, settings.database_uri)

    async with pool_lifespan(
        settings.database_uri,
        min_size=settings.pool_min_size,
        max_size=settings.pool_max_size,
    ) as pool:
        ctx = AppContext(
            agent_task=AgentTaskRepository(pool),
            agent_session=AgentSessionRepository(pool),
            agent_item=AgentItemRepository(pool),
            issue=IssueRepository(pool),
            wiki_page=WikiPageRepository(pool),
        )
        logger.info("document-db-mcp ready (5 collections)")
        yield ctx


# 모듈 레벨 인스턴스 — tools/ 가 import 해서 데코레이터 등록.
# 자원 자체는 lifespan_context 안에 있고, 본 인스턴스는 등록 라우터 역할만.
#
# host="0.0.0.0": 컨테이너 외부 (다른 컨테이너 / 호스트) 에서 접근 허용.
# DNS rebinding 보호는 우리 토폴로지 (내부망 전용) 에서 불필요 → 끄지 않으면
# docker network 의 다른 호스트명에서 차단됨.
_settings_boot = Settings()
mcp = FastMCP(
    "document-db",
    lifespan=_app_lifespan,
    host="0.0.0.0",  # noqa: S104 — 컨테이너 내부 binding, 노출 제어는 compose port mapping 으로
    port=_settings_boot.http_port,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
    ),
)


__all__ = ["AppContext", "mcp"]
