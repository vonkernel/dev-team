"""FastMCP 싱글턴 + lifespan + AppContext."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from wiki_mcp.adapters import Wiki
from wiki_mcp.config import Settings
from wiki_mcp.factory import build_wiki

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AppContext:
    """lifespan 이 yield 하는 의존성 묶음."""

    wiki: Wiki


@asynccontextmanager
async def _app_lifespan(_server: FastMCP) -> AsyncIterator[AppContext]:
    settings = Settings()
    wiki = build_wiki(settings)
    logger.info(
        "wiki-mcp ready (type=%s, target=%s/%s)",
        settings.wiki_type,
        settings.github_target_owner,
        settings.github_target_repo,
    )
    yield AppContext(wiki=wiki)


_settings_boot = Settings()
mcp = FastMCP(
    "wiki",
    lifespan=_app_lifespan,
    host="0.0.0.0",  # noqa: S104 — 컨테이너 내부 binding
    port=_settings_boot.http_port,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
    ),
)


__all__ = ["AppContext", "mcp"]
