"""a2a_task_status_updates MCP 도구 — Task state transition 로그 (immutable)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from dev_team_shared.doc_store.schemas.a2a_task_status_update import (
    A2ATaskStatusUpdateCreate,
    A2ATaskStatusUpdateRead,
)
from dev_team_shared.doc_store.tool_names import A2ATaskStatusUpdateTools
from mcp.server.fastmcp import Context

from doc_store_mcp.mcp_instance import AppContext, mcp
from doc_store_mcp.repositories.base import ListFilter


def _ctx(ctx: Context) -> AppContext:
    return ctx.request_context.lifespan_context  # type: ignore[return-value]


@mcp.tool(name=A2ATaskStatusUpdateTools.CREATE)
async def create(
    ctx: Context, doc: A2ATaskStatusUpdateCreate,
) -> A2ATaskStatusUpdateRead:
    return await _ctx(ctx).a2a_task_status_update.create(doc)


@mcp.tool(name=A2ATaskStatusUpdateTools.GET)
async def get(ctx: Context, id: str) -> A2ATaskStatusUpdateRead | None:
    return await _ctx(ctx).a2a_task_status_update.get(UUID(id))


@mcp.tool(name=A2ATaskStatusUpdateTools.LIST)
async def list_(
    ctx: Context,
    where: dict[str, Any] | None = None,
    limit: int = 200,
    offset: int = 0,
    order_by: str = "transitioned_at",
) -> list[A2ATaskStatusUpdateRead]:
    flt = ListFilter(where=where, limit=limit, offset=offset, order_by=order_by)
    return await _ctx(ctx).a2a_task_status_update.list(flt)


@mcp.tool(name=A2ATaskStatusUpdateTools.DELETE)
async def delete(ctx: Context, id: str) -> bool:
    return await _ctx(ctx).a2a_task_status_update.delete(UUID(id))


@mcp.tool(name=A2ATaskStatusUpdateTools.COUNT)
async def count(ctx: Context, where: dict[str, Any] | None = None) -> int:
    return await _ctx(ctx).a2a_task_status_update.count(where)


@mcp.tool(
    name=A2ATaskStatusUpdateTools.LIST_BY_TASK,
    description="List state transitions of a given a2a_task, ordered by transitioned_at.",
)
async def list_by_task(
    ctx: Context, a2a_task_id: str,
) -> list[A2ATaskStatusUpdateRead]:
    return await _ctx(ctx).a2a_task_status_update.list_by_task(UUID(a2a_task_id))
