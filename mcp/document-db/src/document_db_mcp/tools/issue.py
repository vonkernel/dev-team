"""issues MCP 도구 — 5 op + optimistic locking."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from mcp.server.fastmcp import Context

from document_db_mcp.mcp_instance import AppContext, mcp
from document_db_mcp.repositories.base import ListFilter
from document_db_mcp.repositories.issue import IssueOptimisticLockError
from document_db_mcp.schemas.issue import IssueCreate, IssueUpdate


def _ctx(ctx: Context) -> AppContext:
    return ctx.request_context.lifespan_context  # type: ignore[return-value]


@mcp.tool(
    name="issue.upsert",
    description="Create or update an issue. expected_version for optimistic locking.",
)
async def upsert(
    ctx: Context,
    doc: dict[str, Any],
    id: str | None = None,
    expected_version: int | None = None,
) -> dict[str, Any]:
    repo = _ctx(ctx).issue
    if id:
        patch = IssueUpdate.model_validate(doc)
        try:
            updated = await repo.update_with_version(
                UUID(id), patch, expected_version=expected_version,
            )
        except IssueOptimisticLockError as e:
            raise RuntimeError(str(e)) from e
        if updated is None:
            return (await repo.create(IssueCreate.model_validate(doc))).model_dump(mode="json")
        return updated.model_dump(mode="json")
    return (await repo.create(IssueCreate.model_validate(doc))).model_dump(mode="json")


@mcp.tool(name="issue.get")
async def get(ctx: Context, id: str) -> dict[str, Any] | None:
    result = await _ctx(ctx).issue.get(UUID(id))
    return result.model_dump(mode="json") if result else None


@mcp.tool(name="issue.list")
async def list_(
    ctx: Context,
    where: dict[str, Any] | None = None,
    limit: int = 100,
    offset: int = 0,
    order_by: str = "created_at DESC",
) -> list[dict[str, Any]]:
    flt = ListFilter(where=where, limit=limit, offset=offset, order_by=order_by)
    items = await _ctx(ctx).issue.list(flt)
    return [it.model_dump(mode="json") for it in items]


@mcp.tool(name="issue.delete")
async def delete(ctx: Context, id: str) -> bool:
    return await _ctx(ctx).issue.delete(UUID(id))


@mcp.tool(name="issue.count")
async def count(ctx: Context, where: dict[str, Any] | None = None) -> int:
    return await _ctx(ctx).issue.count(where)
