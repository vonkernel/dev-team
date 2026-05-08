"""a2a_task_artifacts MCP 도구 — Task 산출물 (immutable)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from dev_team_shared.doc_store.schemas.a2a_task_artifact import (
    A2ATaskArtifactCreate,
    A2ATaskArtifactRead,
)
from dev_team_shared.doc_store.tool_names import A2ATaskArtifactTools
from mcp.server.fastmcp import Context

from doc_store_mcp.mcp_instance import AppContext, mcp
from doc_store_mcp.repositories.base import ListFilter


def _ctx(ctx: Context) -> AppContext:
    return ctx.request_context.lifespan_context  # type: ignore[return-value]


@mcp.tool(name=A2ATaskArtifactTools.CREATE)
async def create(
    ctx: Context, doc: A2ATaskArtifactCreate,
) -> A2ATaskArtifactRead:
    return await _ctx(ctx).a2a_task_artifact.create(doc)


@mcp.tool(name=A2ATaskArtifactTools.GET)
async def get(ctx: Context, id: str) -> A2ATaskArtifactRead | None:
    return await _ctx(ctx).a2a_task_artifact.get(UUID(id))


@mcp.tool(name=A2ATaskArtifactTools.LIST)
async def list_(
    ctx: Context,
    where: dict[str, Any] | None = None,
    limit: int = 100,
    offset: int = 0,
    order_by: str = "created_at DESC",
) -> list[A2ATaskArtifactRead]:
    flt = ListFilter(where=where, limit=limit, offset=offset, order_by=order_by)
    return await _ctx(ctx).a2a_task_artifact.list(flt)


@mcp.tool(name=A2ATaskArtifactTools.DELETE)
async def delete(ctx: Context, id: str) -> bool:
    return await _ctx(ctx).a2a_task_artifact.delete(UUID(id))


@mcp.tool(name=A2ATaskArtifactTools.COUNT)
async def count(ctx: Context, where: dict[str, Any] | None = None) -> int:
    return await _ctx(ctx).a2a_task_artifact.count(where)


@mcp.tool(
    name=A2ATaskArtifactTools.LIST_BY_TASK,
    description="List artifacts of a given a2a_task, ordered by created_at.",
)
async def list_by_task(
    ctx: Context, a2a_task_id: str,
) -> list[A2ATaskArtifactRead]:
    return await _ctx(ctx).a2a_task_artifact.list_by_task(UUID(a2a_task_id))
