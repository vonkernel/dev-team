"""agent_sessions MCP 도구."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from dev_team_shared.document_db.schemas.agent_session import (
    AgentSessionCreate,
    AgentSessionRead,
    AgentSessionUpdate,
)
from dev_team_shared.document_db.tool_names import AgentSessionTools
from mcp.server.fastmcp import Context

from document_db_mcp.mcp_instance import AppContext, mcp
from document_db_mcp.repositories.base import ListFilter


def _ctx(ctx: Context) -> AppContext:
    return ctx.request_context.lifespan_context  # type: ignore[return-value]


@mcp.tool(name=AgentSessionTools.CREATE)
async def create(ctx: Context, doc: AgentSessionCreate) -> AgentSessionRead:
    return await _ctx(ctx).agent_session.create(doc)


@mcp.tool(name=AgentSessionTools.UPDATE)
async def update(
    ctx: Context, id: str, patch: AgentSessionUpdate,
) -> AgentSessionRead | None:
    return await _ctx(ctx).agent_session.update(UUID(id), patch)


@mcp.tool(name=AgentSessionTools.GET)
async def get(ctx: Context, id: str) -> AgentSessionRead | None:
    return await _ctx(ctx).agent_session.get(UUID(id))


@mcp.tool(name=AgentSessionTools.LIST)
async def list_(
    ctx: Context,
    where: dict[str, Any] | None = None,
    limit: int = 100,
    offset: int = 0,
    order_by: str = "started_at DESC",
) -> list[AgentSessionRead]:
    flt = ListFilter(where=where, limit=limit, offset=offset, order_by=order_by)
    return await _ctx(ctx).agent_session.list(flt)


@mcp.tool(name=AgentSessionTools.DELETE)
async def delete(ctx: Context, id: str) -> bool:
    return await _ctx(ctx).agent_session.delete(UUID(id))


@mcp.tool(name=AgentSessionTools.COUNT)
async def count(ctx: Context, where: dict[str, Any] | None = None) -> int:
    return await _ctx(ctx).agent_session.count(where)


@mcp.tool(
    name=AgentSessionTools.LIST_BY_TASK,
    description="List sessions in a given agent_task, ordered by started_at.",
)
async def list_by_task(ctx: Context, agent_task_id: str) -> list[AgentSessionRead]:
    return await _ctx(ctx).agent_session.list_by_task(UUID(agent_task_id))


@mcp.tool(
    name=AgentSessionTools.FIND_BY_CONTEXT,
    description="Find the most recent session by A2A context_id.",
)
async def find_by_context(ctx: Context, context_id: str) -> AgentSessionRead | None:
    return await _ctx(ctx).agent_session.find_by_context(context_id)
