"""agent_sessions MCP 도구."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from mcp.server.fastmcp import Context

from document_db_mcp.mcp_instance import AppContext, mcp
from document_db_mcp.repositories.base import ListFilter
from document_db_mcp.schemas.agent_session import AgentSessionCreate, AgentSessionUpdate


def _ctx(ctx: Context) -> AppContext:
    return ctx.request_context.lifespan_context  # type: ignore[return-value]


@mcp.tool(name="agent_session.upsert")
async def upsert(
    ctx: Context,
    doc: dict[str, Any],
    id: str | None = None,
) -> dict[str, Any]:
    repo = _ctx(ctx).agent_session
    if id:
        patch = AgentSessionUpdate.model_validate(doc)
        updated = await repo.update(UUID(id), patch)
        if updated is None:
            return (await repo.create(AgentSessionCreate.model_validate(doc))).model_dump(mode="json")
        return updated.model_dump(mode="json")
    return (await repo.create(AgentSessionCreate.model_validate(doc))).model_dump(mode="json")


@mcp.tool(name="agent_session.get")
async def get(ctx: Context, id: str) -> dict[str, Any] | None:
    result = await _ctx(ctx).agent_session.get(UUID(id))
    return result.model_dump(mode="json") if result else None


@mcp.tool(name="agent_session.list")
async def list_(
    ctx: Context,
    where: dict[str, Any] | None = None,
    limit: int = 100,
    offset: int = 0,
    order_by: str = "started_at DESC",
) -> list[dict[str, Any]]:
    flt = ListFilter(where=where, limit=limit, offset=offset, order_by=order_by)
    items = await _ctx(ctx).agent_session.list(flt)
    return [it.model_dump(mode="json") for it in items]


@mcp.tool(name="agent_session.delete")
async def delete(ctx: Context, id: str) -> bool:
    return await _ctx(ctx).agent_session.delete(UUID(id))


@mcp.tool(name="agent_session.count")
async def count(ctx: Context, where: dict[str, Any] | None = None) -> int:
    return await _ctx(ctx).agent_session.count(where)


@mcp.tool(
    name="agent_session.list_by_task",
    description="List sessions in a given agent_task, ordered by started_at.",
)
async def list_by_task(ctx: Context, agent_task_id: str) -> list[dict[str, Any]]:
    items = await _ctx(ctx).agent_session.list_by_task(UUID(agent_task_id))
    return [it.model_dump(mode="json") for it in items]


@mcp.tool(
    name="agent_session.find_by_context",
    description="Find the most recent session by A2A context_id.",
)
async def find_by_context(ctx: Context, context_id: str) -> dict[str, Any] | None:
    result = await _ctx(ctx).agent_session.find_by_context(context_id)
    return result.model_dump(mode="json") if result else None
