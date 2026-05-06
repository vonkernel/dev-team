"""page.* 도구 — wiki 페이지 CRUD (6 op)."""

from __future__ import annotations

from mcp.server.fastmcp import Context

from dev_team_shared.wiki.schemas import (
    PageCreate,
    PageRead,
    PageRef,
    PageUpdate,
)

from wiki_mcp.mcp_instance import AppContext, mcp


def _ctx(ctx: Context) -> AppContext:
    return ctx.request_context.lifespan_context  # type: ignore[return-value]


@mcp.tool(name="page.create", description="wiki 페이지 생성 (front matter + content)")
async def create_(ctx: Context, doc: PageCreate) -> PageRead:
    return await _ctx(ctx).wiki.pages.create(doc)


@mcp.tool(name="page.update", description="wiki 페이지 갱신 (title / content / metadata)")
async def update(ctx: Context, slug: str, patch: PageUpdate) -> PageRead | None:
    return await _ctx(ctx).wiki.pages.update(slug, patch)


@mcp.tool(name="page.get", description="wiki 페이지 단건 조회 (front matter parse)")
async def get(ctx: Context, slug: str) -> PageRead | None:
    return await _ctx(ctx).wiki.pages.get(slug)


@mcp.tool(name="page.list", description="wiki 페이지 목록 (slug + title 만)")
async def list_(ctx: Context) -> list[PageRef]:
    return await _ctx(ctx).wiki.pages.list()


@mcp.tool(name="page.delete", description="wiki 페이지 삭제")
async def delete(ctx: Context, slug: str) -> bool:
    return await _ctx(ctx).wiki.pages.delete(slug)


@mcp.tool(name="page.count", description="wiki 페이지 개수")
async def count(ctx: Context) -> int:
    return await _ctx(ctx).wiki.pages.count()
