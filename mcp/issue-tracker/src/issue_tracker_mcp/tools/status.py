"""status.* 도구 — 도구가 own 하는 status field options 의 discover + manage.

mcp/CLAUDE.md §0 — 도구 사실 그대로 노출. 정규화 / 매핑 X.
"""

from __future__ import annotations

from mcp.server.fastmcp import Context

from issue_tracker_mcp.mcp_instance import AppContext, mcp
from dev_team_shared.issue_tracker.schemas.refs import StatusRef


def _ctx(ctx: Context) -> AppContext:
    return ctx.request_context.lifespan_context  # type: ignore[return-value]


@mcp.tool(
    name="status.list",
    description="Project board 의 현재 status 목록 (StatusRef.id 가 후속 호출 식별자)",
)
async def list_(ctx: Context) -> list[StatusRef]:
    return await _ctx(ctx).tracker.list_statuses()


@mcp.tool(
    name="status.create",
    description="Project board 에 status option 추가 (이름 중복 시 기존 항목 반환)",
)
async def create_(ctx: Context, name: str) -> StatusRef:
    return await _ctx(ctx).tracker.create_status(name)
