"""agent_items MCP 도구 — items 는 immutable. update/upsert 미노출."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from mcp.server.fastmcp import Context

from document_db_mcp.mcp_instance import AppContext, mcp
from document_db_mcp.repositories.base import ListFilter
from document_db_mcp.schemas.agent_item import AgentItemCreate


def _ctx(ctx: Context) -> AppContext:
    return ctx.request_context.lifespan_context  # type: ignore[return-value]


@mcp.tool(name="agent_item.create", description="Append an item (immutable).")
async def create(ctx: Context, doc: dict[str, Any]) -> dict[str, Any]:
    repo = _ctx(ctx).agent_item
    return (await repo.create(AgentItemCreate.model_validate(doc))).model_dump(mode="json")


@mcp.tool(name="agent_item.get")
async def get(ctx: Context, id: str) -> dict[str, Any] | None:
    result = await _ctx(ctx).agent_item.get(UUID(id))
    return result.model_dump(mode="json") if result else None


@mcp.tool(name="agent_item.list")
async def list_(
    ctx: Context,
    where: dict[str, Any] | None = None,
    limit: int = 200,
    offset: int = 0,
    order_by: str = "created_at",
) -> list[dict[str, Any]]:
    flt = ListFilter(where=where, limit=limit, offset=offset, order_by=order_by)
    items = await _ctx(ctx).agent_item.list(flt)
    return [it.model_dump(mode="json") for it in items]


@mcp.tool(name="agent_item.delete")
async def delete(ctx: Context, id: str) -> bool:
    return await _ctx(ctx).agent_item.delete(UUID(id))


@mcp.tool(name="agent_item.count")
async def count(ctx: Context, where: dict[str, Any] | None = None) -> int:
    return await _ctx(ctx).agent_item.count(where)


@mcp.tool(
    name="agent_item.list_by_session",
    description="List items in a session, ordered by created_at.",
)
async def list_by_session(ctx: Context, agent_session_id: str) -> list[dict[str, Any]]:
    items = await _ctx(ctx).agent_item.list_by_session(UUID(agent_session_id))
    return [it.model_dump(mode="json") for it in items]
