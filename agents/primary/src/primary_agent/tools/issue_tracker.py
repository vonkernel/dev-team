"""IssueTracker MCP 채널 LangChain tools — 외부 GitHub Issue 양방향 동기화.

Primary 가 Doc Store 의 issues 를 외부 IssueTracker 와 sync 하는 도구.
status / type 은 매 프로젝트마다 의미가 다르므로 동적 조회 + 부족 시 도구
안에서 생성 (root CLAUDE.md "에이전트 ↔ 외부 도구 운영 원칙").
"""

from __future__ import annotations

from typing import Any

from dev_team_shared.issue_tracker import (
    IssueCreate,
    IssueRead,
    IssueTrackerClient,
    IssueUpdate,
    StatusRef,
    TypeRef,
)
from langchain_core.tools import BaseTool, tool


def build_issue_tracker_tools(client: IssueTrackerClient) -> list[BaseTool]:
    """IssueTracker 채널의 7 op — issue CRUD + status / type 동적 운용."""

    @tool
    async def external_issue_create(doc: IssueCreate) -> IssueRead:
        """외부 IssueTracker (GitHub Issue) 에 이슈 생성. Doc Store 의 issue 와 sync 시점에 호출."""
        return await client.issues.create(doc)

    @tool
    async def external_issue_update(
        id_or_number: str, patch: IssueUpdate,
    ) -> IssueRead | None:
        """외부 IssueTracker 의 이슈 업데이트 (id 또는 number). status / labels 등 patch."""
        return await client.issues.update(id_or_number, patch)

    @tool
    async def external_issue_list(
        where: dict[str, Any] | None = None,
        limit: int = 100,
    ) -> list[IssueRead]:
        """외부 IssueTracker 이슈 리스트. where 는 backend 별 필터 (state / label 등)."""
        return await client.issues.list(where=where, limit=limit)

    @tool
    async def external_status_list() -> list[StatusRef]:
        """외부 IssueTracker 의 status 목록 동적 조회. LLM 이 의미적 매핑 결정에 사용."""
        return await client.statuses.list()

    @tool
    async def external_status_create(name: str) -> StatusRef:
        """외부 IssueTracker 에 새 status 생성 (현 컨텍스트에 부족할 때)."""
        return await client.statuses.create(name)

    @tool
    async def external_type_list() -> list[TypeRef]:
        """외부 IssueTracker 의 type 목록 동적 조회 (Epic / Story / Task 등)."""
        return await client.types.list()

    @tool
    async def external_type_create(name: str) -> TypeRef:
        """외부 IssueTracker 에 새 type 생성."""
        return await client.types.create(name)

    return [
        external_issue_create,
        external_issue_update,
        external_issue_list,
        external_status_list,
        external_status_create,
        external_type_list,
        external_type_create,
    ]


__all__ = ["build_issue_tracker_tools"]
