"""assignments MCP 도구 — chat tier 의 도메인 work item."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from dev_team_shared.doc_store.schemas.assignment import (
    AssignmentCreate,
    AssignmentRead,
    AssignmentUpdate,
)
from dev_team_shared.doc_store.tool_names import AssignmentTools
from mcp.server.fastmcp import Context

from doc_store_mcp.mcp_instance import AppContext, mcp
from doc_store_mcp.repositories.base import ListFilter


def _ctx(ctx: Context) -> AppContext:
    return ctx.request_context.lifespan_context  # type: ignore[return-value]


@mcp.tool(name=AssignmentTools.CREATE)
async def create(ctx: Context, doc: AssignmentCreate) -> AssignmentRead:
    return await _ctx(ctx).assignment.create(doc)


@mcp.tool(name=AssignmentTools.UPDATE)
async def update(
    ctx: Context, id: str, patch: AssignmentUpdate,
) -> AssignmentRead | None:
    return await _ctx(ctx).assignment.update(UUID(id), patch)


@mcp.tool(name=AssignmentTools.GET)
async def get(ctx: Context, id: str) -> AssignmentRead | None:
    return await _ctx(ctx).assignment.get(UUID(id))


@mcp.tool(name=AssignmentTools.LIST)
async def list_(
    ctx: Context,
    where: dict[str, Any] | None = None,
    limit: int = 100,
    offset: int = 0,
    order_by: str = "created_at DESC",
) -> list[AssignmentRead]:
    flt = ListFilter(where=where, limit=limit, offset=offset, order_by=order_by)
    return await _ctx(ctx).assignment.list(flt)


@mcp.tool(name=AssignmentTools.DELETE)
async def delete(ctx: Context, id: str) -> bool:
    return await _ctx(ctx).assignment.delete(UUID(id))


@mcp.tool(name=AssignmentTools.COUNT)
async def count(ctx: Context, where: dict[str, Any] | None = None) -> int:
    return await _ctx(ctx).assignment.count(where)


@mcp.tool(
    name=AssignmentTools.LIST_BY_SESSION,
    description="List assignments derived from a given session.",
)
async def list_by_session(
    ctx: Context, root_session_id: str,
) -> list[AssignmentRead]:
    return await _ctx(ctx).assignment.list_by_session(UUID(root_session_id))
