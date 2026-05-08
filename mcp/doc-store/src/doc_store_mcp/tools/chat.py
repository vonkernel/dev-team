"""chats MCP 도구 — chat tier 의 메시지 (immutable)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from dev_team_shared.doc_store.schemas.chat import ChatCreate, ChatRead
from dev_team_shared.doc_store.tool_names import ChatTools
from mcp.server.fastmcp import Context

from doc_store_mcp.mcp_instance import AppContext, mcp
from doc_store_mcp.repositories.base import ListFilter


def _ctx(ctx: Context) -> AppContext:
    return ctx.request_context.lifespan_context  # type: ignore[return-value]


@mcp.tool(name=ChatTools.CREATE)
async def create(ctx: Context, doc: ChatCreate) -> ChatRead:
    return await _ctx(ctx).chat.create(doc)


@mcp.tool(name=ChatTools.GET)
async def get(ctx: Context, id: str) -> ChatRead | None:
    return await _ctx(ctx).chat.get(UUID(id))


@mcp.tool(name=ChatTools.LIST)
async def list_(
    ctx: Context,
    where: dict[str, Any] | None = None,
    limit: int = 200,
    offset: int = 0,
    order_by: str = "created_at",
) -> list[ChatRead]:
    flt = ListFilter(where=where, limit=limit, offset=offset, order_by=order_by)
    return await _ctx(ctx).chat.list(flt)


@mcp.tool(name=ChatTools.DELETE)
async def delete(ctx: Context, id: str) -> bool:
    return await _ctx(ctx).chat.delete(UUID(id))


@mcp.tool(name=ChatTools.COUNT)
async def count(ctx: Context, where: dict[str, Any] | None = None) -> int:
    return await _ctx(ctx).chat.count(where)


@mcp.tool(
    name=ChatTools.LIST_BY_SESSION,
    description="List chats in a given session, ordered by created_at.",
)
async def list_by_session(ctx: Context, session_id: str) -> list[ChatRead]:
    return await _ctx(ctx).chat.list_by_session(UUID(session_id))
