"""a2a_tasks MCP 도구 — A2A Task (stateful work)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from dev_team_shared.doc_store.schemas.a2a_task import (
    A2ATaskCreate,
    A2ATaskRead,
    A2ATaskUpdate,
)
from dev_team_shared.doc_store.tool_names import A2ATaskTools
from mcp.server.fastmcp import Context

from doc_store_mcp.mcp_instance import AppContext, mcp
from doc_store_mcp.repositories.base import ListFilter


def _ctx(ctx: Context) -> AppContext:
    return ctx.request_context.lifespan_context  # type: ignore[return-value]


@mcp.tool(name=A2ATaskTools.CREATE)
async def create(ctx: Context, doc: A2ATaskCreate) -> A2ATaskRead:
    return await _ctx(ctx).a2a_task.create(doc)


@mcp.tool(name=A2ATaskTools.UPDATE)
async def update(
    ctx: Context, id: str, patch: A2ATaskUpdate,
) -> A2ATaskRead | None:
    return await _ctx(ctx).a2a_task.update(UUID(id), patch)


@mcp.tool(name=A2ATaskTools.GET)
async def get(ctx: Context, id: str) -> A2ATaskRead | None:
    return await _ctx(ctx).a2a_task.get(UUID(id))


@mcp.tool(name=A2ATaskTools.LIST)
async def list_(
    ctx: Context,
    where: dict[str, Any] | None = None,
    limit: int = 100,
    offset: int = 0,
    order_by: str = "submitted_at DESC",
) -> list[A2ATaskRead]:
    flt = ListFilter(where=where, limit=limit, offset=offset, order_by=order_by)
    return await _ctx(ctx).a2a_task.list(flt)


@mcp.tool(name=A2ATaskTools.DELETE)
async def delete(ctx: Context, id: str) -> bool:
    return await _ctx(ctx).a2a_task.delete(UUID(id))


@mcp.tool(name=A2ATaskTools.COUNT)
async def count(ctx: Context, where: dict[str, Any] | None = None) -> int:
    return await _ctx(ctx).a2a_task.count(where)


@mcp.tool(
    name=A2ATaskTools.FIND_BY_TASK_ID,
    description="Find the most recent a2a_task by A2A wire task_id.",
)
async def find_by_task_id(ctx: Context, task_id: str) -> A2ATaskRead | None:
    return await _ctx(ctx).a2a_task.find_by_task_id(task_id)
