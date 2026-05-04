"""type.* 도구 — 도구가 own 하는 type field options 의 discover + manage."""

from __future__ import annotations

from mcp.server.fastmcp import Context

from issue_tracker_mcp.mcp_instance import AppContext, mcp
from dev_team_shared.issue_tracker.schemas.refs import TypeRef


def _ctx(ctx: Context) -> AppContext:
    return ctx.request_context.lifespan_context  # type: ignore[return-value]


@mcp.tool(
    name="type.list",
    description="Project board 의 현재 issue type 목록",
)
async def list_(ctx: Context) -> list[TypeRef]:
    return await _ctx(ctx).tracker.list_types()


@mcp.tool(
    name="type.create",
    description="Project board 에 type option 추가 (이름 중복 시 기존 항목 반환)",
)
async def create_(ctx: Context, name: str) -> TypeRef:
    return await _ctx(ctx).tracker.create_type(name)
