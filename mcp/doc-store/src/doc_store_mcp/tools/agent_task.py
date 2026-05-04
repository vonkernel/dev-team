"""agent_tasks MCP 도구 — Pydantic 파라미터 직접 (mcp/CLAUDE.md §1.3.1).

도구명은 shared 의 AgentTaskTools 상수 (단일 source of truth — server / client 공유).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from dev_team_shared.doc_store.schemas.agent_task import (
    AgentTaskCreate,
    AgentTaskRead,
    AgentTaskUpdate,
)
from dev_team_shared.doc_store.tool_names import AgentTaskTools
from mcp.server.fastmcp import Context

from doc_store_mcp.mcp_instance import AppContext, mcp
from doc_store_mcp.repositories.base import ListFilter


def _ctx(ctx: Context) -> AppContext:
    return ctx.request_context.lifespan_context  # type: ignore[return-value]


@mcp.tool(name=AgentTaskTools.CREATE, description="Create a new agent_task.")
async def create(ctx: Context, doc: AgentTaskCreate) -> AgentTaskRead:
    return await _ctx(ctx).agent_task.create(doc)


@mcp.tool(name=AgentTaskTools.UPDATE, description="Patch update an agent_task by id.")
async def update(ctx: Context, id: str, patch: AgentTaskUpdate) -> AgentTaskRead | None:
    return await _ctx(ctx).agent_task.update(UUID(id), patch)


@mcp.tool(name=AgentTaskTools.GET, description="Get an agent_task by id.")
async def get(ctx: Context, id: str) -> AgentTaskRead | None:
    return await _ctx(ctx).agent_task.get(UUID(id))


@mcp.tool(name=AgentTaskTools.LIST, description="List agent_tasks with optional filter.")
async def list_(
    ctx: Context,
    where: dict[str, Any] | None = None,
    limit: int = 100,
    offset: int = 0,
    order_by: str = "created_at DESC",
) -> list[AgentTaskRead]:
    flt = ListFilter(where=where, limit=limit, offset=offset, order_by=order_by)
    return await _ctx(ctx).agent_task.list(flt)


@mcp.tool(name=AgentTaskTools.DELETE, description="Delete an agent_task by id.")
async def delete(ctx: Context, id: str) -> bool:
    return await _ctx(ctx).agent_task.delete(UUID(id))


@mcp.tool(name=AgentTaskTools.COUNT, description="Count agent_tasks with optional filter.")
async def count(ctx: Context, where: dict[str, Any] | None = None) -> int:
    return await _ctx(ctx).agent_task.count(where)
