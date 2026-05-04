"""agent_tasks MCP 도구."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from mcp.server.fastmcp import Context

from document_db_mcp.mcp_instance import AppContext, mcp
from document_db_mcp.repositories.base import ListFilter
from document_db_mcp.schemas.agent_task import AgentTaskCreate, AgentTaskUpdate


def _ctx(ctx: Context) -> AppContext:
    """lifespan 의 AppContext 를 꺼냄. type-narrowed alias."""
    return ctx.request_context.lifespan_context  # type: ignore[return-value]


@mcp.tool(name="agent_task.upsert", description="Create or update an agent_task.")
async def upsert(
    ctx: Context,
    doc: dict[str, Any],
    id: str | None = None,
) -> dict[str, Any]:
    repo = _ctx(ctx).agent_task
    if id:
        patch = AgentTaskUpdate.model_validate(doc)
        updated = await repo.update(UUID(id), patch)
        if updated is None:
            return (await repo.create(AgentTaskCreate.model_validate(doc))).model_dump(mode="json")
        return updated.model_dump(mode="json")
    return (await repo.create(AgentTaskCreate.model_validate(doc))).model_dump(mode="json")


@mcp.tool(name="agent_task.get", description="Get an agent_task by id.")
async def get(ctx: Context, id: str) -> dict[str, Any] | None:
    result = await _ctx(ctx).agent_task.get(UUID(id))
    return result.model_dump(mode="json") if result else None


@mcp.tool(name="agent_task.list", description="List agent_tasks with optional filter.")
async def list_(
    ctx: Context,
    where: dict[str, Any] | None = None,
    limit: int = 100,
    offset: int = 0,
    order_by: str = "created_at DESC",
) -> list[dict[str, Any]]:
    flt = ListFilter(where=where, limit=limit, offset=offset, order_by=order_by)
    items = await _ctx(ctx).agent_task.list(flt)
    return [it.model_dump(mode="json") for it in items]


@mcp.tool(name="agent_task.delete", description="Delete an agent_task by id.")
async def delete(ctx: Context, id: str) -> bool:
    return await _ctx(ctx).agent_task.delete(UUID(id))


@mcp.tool(name="agent_task.count", description="Count agent_tasks.")
async def count(ctx: Context, where: dict[str, Any] | None = None) -> int:
    return await _ctx(ctx).agent_task.count(where)
