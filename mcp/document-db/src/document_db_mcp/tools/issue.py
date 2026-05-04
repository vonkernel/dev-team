"""issues MCP 도구 — create + update 분리, optimistic locking."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from mcp.server.fastmcp import Context

from document_db_mcp.mcp_instance import AppContext, mcp
from document_db_mcp.repositories.base import ListFilter
from document_db_mcp.repositories.issue import IssueOptimisticLockError
from document_db_mcp.schemas.issue import IssueCreate, IssueRead, IssueUpdate


def _ctx(ctx: Context) -> AppContext:
    return ctx.request_context.lifespan_context  # type: ignore[return-value]


@mcp.tool(name="issue.create", description="Create a new issue.")
async def create(ctx: Context, doc: IssueCreate) -> IssueRead:
    return await _ctx(ctx).issue.create(doc)


@mcp.tool(
    name="issue.update",
    description="Patch update an issue. expected_version for optimistic locking.",
)
async def update(
    ctx: Context,
    id: str,
    patch: IssueUpdate,
    expected_version: int | None = None,
) -> IssueRead | None:
    try:
        return await _ctx(ctx).issue.update_with_version(
            UUID(id), patch, expected_version=expected_version,
        )
    except IssueOptimisticLockError as e:
        raise RuntimeError(str(e)) from e


@mcp.tool(name="issue.get")
async def get(ctx: Context, id: str) -> IssueRead | None:
    return await _ctx(ctx).issue.get(UUID(id))


@mcp.tool(name="issue.list")
async def list_(
    ctx: Context,
    where: dict[str, Any] | None = None,
    limit: int = 100,
    offset: int = 0,
    order_by: str = "created_at DESC",
) -> list[IssueRead]:
    flt = ListFilter(where=where, limit=limit, offset=offset, order_by=order_by)
    return await _ctx(ctx).issue.list(flt)


@mcp.tool(name="issue.delete")
async def delete(ctx: Context, id: str) -> bool:
    return await _ctx(ctx).issue.delete(UUID(id))


@mcp.tool(name="issue.count")
async def count(ctx: Context, where: dict[str, Any] | None = None) -> int:
    return await _ctx(ctx).issue.count(where)
