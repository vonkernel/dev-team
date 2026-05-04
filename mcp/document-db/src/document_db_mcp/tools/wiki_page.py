"""wiki_pages MCP 도구 — 5 op + get_by_slug + optimistic locking."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from mcp.server.fastmcp import Context

from document_db_mcp.mcp_instance import AppContext, mcp
from document_db_mcp.repositories.base import ListFilter
from document_db_mcp.repositories.wiki_page import WikiPageOptimisticLockError
from document_db_mcp.schemas.wiki_page import WikiPageCreate, WikiPageUpdate


def _ctx(ctx: Context) -> AppContext:
    return ctx.request_context.lifespan_context  # type: ignore[return-value]


@mcp.tool(
    name="wiki_page.upsert",
    description="Create or update a wiki page. expected_version for optimistic locking.",
)
async def upsert(
    ctx: Context,
    doc: dict[str, Any],
    id: str | None = None,
    expected_version: int | None = None,
) -> dict[str, Any]:
    repo = _ctx(ctx).wiki_page
    if id:
        patch = WikiPageUpdate.model_validate(doc)
        try:
            updated = await repo.update_with_version(
                UUID(id), patch, expected_version=expected_version,
            )
        except WikiPageOptimisticLockError as e:
            raise RuntimeError(str(e)) from e
        if updated is None:
            return (await repo.create(WikiPageCreate.model_validate(doc))).model_dump(mode="json")
        return updated.model_dump(mode="json")
    return (await repo.create(WikiPageCreate.model_validate(doc))).model_dump(mode="json")


@mcp.tool(name="wiki_page.get")
async def get(ctx: Context, id: str) -> dict[str, Any] | None:
    result = await _ctx(ctx).wiki_page.get(UUID(id))
    return result.model_dump(mode="json") if result else None


@mcp.tool(name="wiki_page.list")
async def list_(
    ctx: Context,
    where: dict[str, Any] | None = None,
    limit: int = 100,
    offset: int = 0,
    order_by: str = "created_at DESC",
) -> list[dict[str, Any]]:
    flt = ListFilter(where=where, limit=limit, offset=offset, order_by=order_by)
    items = await _ctx(ctx).wiki_page.list(flt)
    return [it.model_dump(mode="json") for it in items]


@mcp.tool(name="wiki_page.delete")
async def delete(ctx: Context, id: str) -> bool:
    return await _ctx(ctx).wiki_page.delete(UUID(id))


@mcp.tool(name="wiki_page.count")
async def count(ctx: Context, where: dict[str, Any] | None = None) -> int:
    return await _ctx(ctx).wiki_page.count(where)


@mcp.tool(name="wiki_page.get_by_slug", description="Get a wiki page by its slug.")
async def get_by_slug(ctx: Context, slug: str) -> dict[str, Any] | None:
    result = await _ctx(ctx).wiki_page.get_by_slug(slug)
    return result.model_dump(mode="json") if result else None
