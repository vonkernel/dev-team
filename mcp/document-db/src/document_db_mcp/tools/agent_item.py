"""agent_items MCP 도구 — items 는 immutable. update 미노출."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from dev_team_shared.document_db.schemas.agent_item import AgentItemCreate, AgentItemRead
from dev_team_shared.document_db.tool_names import AgentItemTools
from mcp.server.fastmcp import Context

from document_db_mcp.mcp_instance import AppContext, mcp
from document_db_mcp.repositories.base import ListFilter


def _ctx(ctx: Context) -> AppContext:
    return ctx.request_context.lifespan_context  # type: ignore[return-value]


@mcp.tool(name=AgentItemTools.CREATE, description="Append an item (immutable).")
async def create(ctx: Context, doc: AgentItemCreate) -> AgentItemRead:
    return await _ctx(ctx).agent_item.create(doc)


@mcp.tool(name=AgentItemTools.GET)
async def get(ctx: Context, id: str) -> AgentItemRead | None:
    return await _ctx(ctx).agent_item.get(UUID(id))


@mcp.tool(name=AgentItemTools.LIST)
async def list_(
    ctx: Context,
    where: dict[str, Any] | None = None,
    limit: int = 200,
    offset: int = 0,
    order_by: str = "created_at",
) -> list[AgentItemRead]:
    flt = ListFilter(where=where, limit=limit, offset=offset, order_by=order_by)
    return await _ctx(ctx).agent_item.list(flt)


@mcp.tool(name=AgentItemTools.DELETE)
async def delete(ctx: Context, id: str) -> bool:
    return await _ctx(ctx).agent_item.delete(UUID(id))


@mcp.tool(name=AgentItemTools.COUNT)
async def count(ctx: Context, where: dict[str, Any] | None = None) -> int:
    return await _ctx(ctx).agent_item.count(where)


@mcp.tool(
    name=AgentItemTools.LIST_BY_SESSION,
    description="List items in a session, ordered by created_at.",
)
async def list_by_session(ctx: Context, agent_session_id: str) -> list[AgentItemRead]:
    return await _ctx(ctx).agent_item.list_by_session(UUID(agent_session_id))
