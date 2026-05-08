"""sessions MCP 도구 — chat tier (UG↔P/A 한 대화창)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from dev_team_shared.doc_store.schemas.session import (
    SessionCreate,
    SessionRead,
    SessionUpdate,
)
from dev_team_shared.doc_store.tool_names import SessionTools
from mcp.server.fastmcp import Context

from doc_store_mcp.mcp_instance import AppContext, mcp
from doc_store_mcp.repositories.base import ListFilter


def _ctx(ctx: Context) -> AppContext:
    return ctx.request_context.lifespan_context  # type: ignore[return-value]


@mcp.tool(name=SessionTools.CREATE)
async def create(ctx: Context, doc: SessionCreate) -> SessionRead:
    return await _ctx(ctx).session.create(doc)


@mcp.tool(name=SessionTools.UPDATE)
async def update(ctx: Context, id: str, patch: SessionUpdate) -> SessionRead | None:
    return await _ctx(ctx).session.update(UUID(id), patch)


@mcp.tool(name=SessionTools.GET)
async def get(ctx: Context, id: str) -> SessionRead | None:
    return await _ctx(ctx).session.get(UUID(id))


@mcp.tool(name=SessionTools.LIST)
async def list_(
    ctx: Context,
    where: dict[str, Any] | None = None,
    limit: int = 100,
    offset: int = 0,
    order_by: str = "started_at DESC",
) -> list[SessionRead]:
    flt = ListFilter(where=where, limit=limit, offset=offset, order_by=order_by)
    return await _ctx(ctx).session.list(flt)


@mcp.tool(name=SessionTools.DELETE)
async def delete(ctx: Context, id: str) -> bool:
    return await _ctx(ctx).session.delete(UUID(id))


@mcp.tool(name=SessionTools.COUNT)
async def count(ctx: Context, where: dict[str, Any] | None = None) -> int:
    return await _ctx(ctx).session.count(where)
