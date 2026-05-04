"""FastMCP 싱글턴 + lifespan + AppContext.

본 모듈이 `mcp` 인스턴스를 노출. tools/ 의 각 모듈이 본 인스턴스를 import 해
`@mcp.tool()` 로 도구 등록. lifespan 은 어댑터를 만들어 AppContext 로 yield →
도구는 `ctx.request_context.lifespan_context.tracker` 로 접근.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from issue_tracker_mcp.adapters import IssueTracker
from issue_tracker_mcp.config import Settings
from issue_tracker_mcp.factory import build_tracker

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AppContext:
    """lifespan 이 yield 하는 의존성 묶음."""

    tracker: IssueTracker


@asynccontextmanager
async def _app_lifespan(_server: FastMCP) -> AsyncIterator[AppContext]:
    settings = Settings()
    tracker, aclose = build_tracker(settings)
    logger.info(
        "issue-tracker-mcp ready (type=%s, target=%s/%s, project=%s)",
        settings.issue_tracker_type,
        settings.github_target_owner,
        settings.github_target_repo,
        settings.github_project_number,
    )
    try:
        yield AppContext(tracker=tracker)
    finally:
        # http 클라이언트 등 자원 해제. aclose 는 awaitable 또는 동기 — 둘 다 처리.
        result = aclose()
        if hasattr(result, "__await__"):
            await result  # type: ignore[func-returns-value]


_settings_boot = Settings()
mcp = FastMCP(
    "issue-tracker",
    lifespan=_app_lifespan,
    host="0.0.0.0",  # noqa: S104 — 컨테이너 내부 binding, 노출 제어는 compose
    port=_settings_boot.http_port,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
    ),
)


__all__ = ["AppContext", "mcp"]
