"""field.* 도구 — board 의 field 자체 (Status / Type / Priority 등) discover + manage.

P (LLM 에이전트) 가 board 셋업 단계에서 사용. 도구 사용 워크플로:
1. `field.list` → board 의 field 현황 확인
2. 필요한 field (예: "Status" / "Type") 가 없으면 `field.create` 로 추가
3. `status.list` / `type.list` 로 옵션 점검 → 부족하면 `*.create`
4. 이슈 작업 진행
"""

from __future__ import annotations

from mcp.server.fastmcp import Context

from dev_team_shared.issue_tracker.schemas.refs import FieldRef
from issue_tracker_mcp.mcp_instance import AppContext, mcp


def _ctx(ctx: Context) -> AppContext:
    return ctx.request_context.lifespan_context  # type: ignore[return-value]


@mcp.tool(
    name="field.list",
    description="Project board 의 모든 field 목록 (Status / Type / Priority 등)",
)
async def list_(ctx: Context) -> list[FieldRef]:
    return await _ctx(ctx).tracker.list_fields()


@mcp.tool(
    name="field.create",
    description=(
        "Project board 에 field 추가. kind 기본 'single_select' "
        "(다른 옵션: text / number / date / iteration). 이름 중복 시 기존 항목 반환."
    ),
)
async def create_(ctx: Context, name: str, kind: str = "single_select") -> FieldRef:
    return await _ctx(ctx).tracker.create_field(name, kind)
