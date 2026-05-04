"""wiki_pages MCP 도구 — create + update + get_by_slug, optimistic locking."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from dev_team_shared.document_db.schemas.wiki_page import (
    WikiPageCreate,
    WikiPageRead,
    WikiPageUpdate,
)
from dev_team_shared.document_db.tool_names import WikiPageTools
from mcp.server.fastmcp import Context

from document_db_mcp.mcp_instance import AppContext, mcp
from document_db_mcp.repositories.base import ListFilter
from document_db_mcp.repositories.wiki_page import WikiPageOptimisticLockError


def _ctx(ctx: Context) -> AppContext:
    return ctx.request_context.lifespan_context  # type: ignore[return-value]


@mcp.tool(name=WikiPageTools.CREATE, description="Create a new wiki page.")
async def create(ctx: Context, doc: WikiPageCreate) -> WikiPageRead:
    return await _ctx(ctx).wiki_page.create(doc)


@mcp.tool(
    name=WikiPageTools.UPDATE,
    description="Patch update a wiki page. expected_version for optimistic locking.",
)
async def update(
    ctx: Context,
    id: str,
    patch: WikiPageUpdate,
    expected_version: int | None = None,
) -> WikiPageRead | None:
    try:
        return await _ctx(ctx).wiki_page.update_with_version(
            UUID(id), patch, expected_version=expected_version,
        )
    except WikiPageOptimisticLockError as e:
        raise RuntimeError(str(e)) from e


@mcp.tool(name=WikiPageTools.GET)
async def get(ctx: Context, id: str) -> WikiPageRead | None:
    return await _ctx(ctx).wiki_page.get(UUID(id))


@mcp.tool(name=WikiPageTools.LIST)
async def list_(
    ctx: Context,
    where: dict[str, Any] | None = None,
    limit: int = 100,
    offset: int = 0,
    order_by: str = "created_at DESC",
) -> list[WikiPageRead]:
    flt = ListFilter(where=where, limit=limit, offset=offset, order_by=order_by)
    return await _ctx(ctx).wiki_page.list(flt)


@mcp.tool(name=WikiPageTools.DELETE)
async def delete(ctx: Context, id: str) -> bool:
    return await _ctx(ctx).wiki_page.delete(UUID(id))


@mcp.tool(name=WikiPageTools.COUNT)
async def count(ctx: Context, where: dict[str, Any] | None = None) -> int:
    return await _ctx(ctx).wiki_page.count(where)


@mcp.tool(name=WikiPageTools.GET_BY_SLUG, description="Get a wiki page by its slug.")
async def get_by_slug(ctx: Context, slug: str) -> WikiPageRead | None:
    return await _ctx(ctx).wiki_page.get_by_slug(slug)
