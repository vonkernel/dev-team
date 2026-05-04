"""issue.* 도구 — CRUD + transition + close.

mcp/CLAUDE.md §1.3.1 — Pydantic 파라미터 / 반환 직접 사용.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context

from issue_tracker_mcp.mcp_instance import AppContext, mcp
from dev_team_shared.issue_tracker.schemas.issue import IssueCreate, IssueRead, IssueUpdate


def _ctx(ctx: Context) -> AppContext:
    return ctx.request_context.lifespan_context  # type: ignore[return-value]


@mcp.tool(name="issue.create", description="이슈 생성 (Project board 자동 등록)")
async def create_(ctx: Context, doc: IssueCreate) -> IssueRead:
    return await _ctx(ctx).tracker.issues.create(doc)


@mcp.tool(name="issue.update", description="이슈 갱신 (title / body / type)")
async def update(ctx: Context, ref: str, patch: IssueUpdate) -> IssueRead | None:
    return await _ctx(ctx).tracker.issues.update(ref, patch)


@mcp.tool(name="issue.get", description="이슈 단건 조회")
async def get(ctx: Context, ref: str) -> IssueRead | None:
    return await _ctx(ctx).tracker.issues.get(ref)


@mcp.tool(name="issue.list", description="이슈 목록 (where 단순 equality 필터)")
async def list_(
    ctx: Context,
    where: dict[str, Any] | None = None,
    limit: int = 100,
    offset: int = 0,
    order_by: str = "created_at desc",
) -> list[IssueRead]:
    return await _ctx(ctx).tracker.issues.list(where, limit, offset, order_by)


@mcp.tool(name="issue.close", description="이슈 close (lifecycle 종료, 보존)")
async def close(ctx: Context, ref: str) -> bool:
    return await _ctx(ctx).tracker.issues.close(ref)


@mcp.tool(
    name="issue.delete",
    description=(
        "이슈 영구 삭제 (테스트 정리 / 실수 회복용). "
        "GitHub 의 경우 repo admin 권한 필요 — 권한 없으면 에러. "
        "일반 lifecycle 종료엔 issue.close 사용."
    ),
)
async def delete(ctx: Context, ref: str) -> bool:
    return await _ctx(ctx).tracker.issues.delete(ref)


@mcp.tool(name="issue.count", description="이슈 개수 (where 필터 적용)")
async def count(ctx: Context, where: dict[str, Any] | None = None) -> int:
    return await _ctx(ctx).tracker.issues.count(where)


@mcp.tool(
    name="issue.transition",
    description=(
        "이슈의 status 전이. status_id 는 status.list 결과의 StatusRef.id."
    ),
)
async def transition(ctx: Context, ref: str, status_id: str) -> None:
    await _ctx(ctx).tracker.issues.transition(ref, status_id)
