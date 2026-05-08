"""a2a_messages MCP 도구 — A2A Message (immutable)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from dev_team_shared.doc_store.schemas.a2a_message import (
    A2AMessageCreate,
    A2AMessageRead,
)
from dev_team_shared.doc_store.tool_names import A2AMessageTools
from mcp.server.fastmcp import Context

from doc_store_mcp.mcp_instance import AppContext, mcp
from doc_store_mcp.repositories.base import ListFilter


def _ctx(ctx: Context) -> AppContext:
    return ctx.request_context.lifespan_context  # type: ignore[return-value]


@mcp.tool(name=A2AMessageTools.CREATE)
async def create(ctx: Context, doc: A2AMessageCreate) -> A2AMessageRead:
    return await _ctx(ctx).a2a_message.create(doc)


@mcp.tool(name=A2AMessageTools.GET)
async def get(ctx: Context, id: str) -> A2AMessageRead | None:
    return await _ctx(ctx).a2a_message.get(UUID(id))


@mcp.tool(name=A2AMessageTools.LIST)
async def list_(
    ctx: Context,
    where: dict[str, Any] | None = None,
    limit: int = 200,
    offset: int = 0,
    order_by: str = "created_at",
) -> list[A2AMessageRead]:
    flt = ListFilter(where=where, limit=limit, offset=offset, order_by=order_by)
    return await _ctx(ctx).a2a_message.list(flt)


@mcp.tool(name=A2AMessageTools.DELETE)
async def delete(ctx: Context, id: str) -> bool:
    return await _ctx(ctx).a2a_message.delete(UUID(id))


@mcp.tool(name=A2AMessageTools.COUNT)
async def count(ctx: Context, where: dict[str, Any] | None = None) -> int:
    return await _ctx(ctx).a2a_message.count(where)


@mcp.tool(
    name=A2AMessageTools.LIST_BY_CONTEXT,
    description="List messages within a given a2a_context, ordered by created_at.",
)
async def list_by_context(
    ctx: Context, a2a_context_id: str,
) -> list[A2AMessageRead]:
    return await _ctx(ctx).a2a_message.list_by_context(UUID(a2a_context_id))


@mcp.tool(
    name=A2AMessageTools.LIST_BY_TASK,
    description="List Task.history messages of a given a2a_task, ordered by created_at.",
)
async def list_by_task(ctx: Context, a2a_task_id: str) -> list[A2AMessageRead]:
    return await _ctx(ctx).a2a_message.list_by_task(UUID(a2a_task_id))
