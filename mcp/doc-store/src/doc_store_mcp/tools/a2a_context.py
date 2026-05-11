"""a2a_contexts MCP 도구 — A2A tier 의 두 에이전트 사이 대화 namespace."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from dev_team_shared.doc_store.schemas.a2a_context import (
    A2AContextCreate,
    A2AContextRead,
    A2AContextUpdate,
)
from dev_team_shared.doc_store.tool_names import A2AContextTools
from mcp.server.fastmcp import Context

from doc_store_mcp.mcp_instance import AppContext, mcp
from doc_store_mcp.repositories.base import ListFilter


def _ctx(ctx: Context) -> AppContext:
    return ctx.request_context.lifespan_context  # type: ignore[return-value]


@mcp.tool(name=A2AContextTools.CREATE)
async def create(ctx: Context, doc: A2AContextCreate) -> A2AContextRead:
    return await _ctx(ctx).a2a_context.create(doc)


@mcp.tool(name=A2AContextTools.UPDATE)
async def update(
    ctx: Context, id: str, patch: A2AContextUpdate,
) -> A2AContextRead | None:
    return await _ctx(ctx).a2a_context.update(UUID(id), patch)


@mcp.tool(name=A2AContextTools.GET)
async def get(ctx: Context, id: str) -> A2AContextRead | None:
    return await _ctx(ctx).a2a_context.get(UUID(id))


@mcp.tool(name=A2AContextTools.LIST)
async def list_(
    ctx: Context,
    where: dict[str, Any] | None = None,
    limit: int = 100,
    offset: int = 0,
    order_by: str = "started_at DESC",
) -> list[A2AContextRead]:
    flt = ListFilter(where=where, limit=limit, offset=offset, order_by=order_by)
    return await _ctx(ctx).a2a_context.list(flt)


@mcp.tool(name=A2AContextTools.DELETE)
async def delete(ctx: Context, id: str) -> bool:
    return await _ctx(ctx).a2a_context.delete(UUID(id))


@mcp.tool(name=A2AContextTools.COUNT)
async def count(ctx: Context, where: dict[str, Any] | None = None) -> int:
    return await _ctx(ctx).a2a_context.count(where)

# find_by_context_id 폐기 (#75 PR 4) — wire context_id 컬럼 자체 폐기.
# caller 는 publisher-supplied UUID 알면 a2a_context.get(id) 호출.
