"""Doc Store MCP 채널 LangChain tools.

Primary 자기 도메인 (Assignment / PRD / Epic / Story / Wiki) 의 직접 write /
read. #75 재설계로 agent_tasks 가 assignments 로 재정의됨.

PR 4: Assignment 도구 추가 (assignment_create / assignment_update / assignment_get
/ assignment_list). 발급은 **사용자와 명시적 합의 후에만** — Primary persona
의 "Assignment 발급 — 명시적 합의 후에만" 섹션 참조.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from dev_team_shared.doc_store import (
    AssignmentCreate,
    AssignmentRead,
    AssignmentUpdate,
    DocStoreClient,
    IssueCreate,
    IssueRead,
    IssueUpdate,
    WikiPageCreate,
    WikiPageRead,
    WikiPageUpdate,
)
from langchain_core.tools import BaseTool, tool


def build_doc_store_tools(client: DocStoreClient) -> list[BaseTool]:
    """Doc Store 채널의 LangChain tool 묶음."""

    @tool
    async def wiki_pages_create(doc: WikiPageCreate) -> WikiPageRead:
        """Doc Store 에 wiki page 생성 (PRD / ADR / business_rule 등). page_type 필드로 분류."""
        return await client.wiki_page_create(doc)

    @tool
    async def wiki_pages_update(id: str, patch: WikiPageUpdate) -> WikiPageRead | None:
        """Doc Store 의 wiki page 업데이트 (UUID). status patch 등에 사용. 미존재 시 null."""
        return await client.wiki_page_update(UUID(id), patch)

    @tool
    async def wiki_pages_get(id: str) -> WikiPageRead | None:
        """Doc Store 의 wiki page 조회 (UUID). 미존재 시 null."""
        return await client.wiki_page_get(UUID(id))

    @tool
    async def wiki_pages_get_by_slug(slug: str) -> WikiPageRead | None:
        """Doc Store 의 wiki page 를 slug 로 조회 (예: 'prd-guestbook'). 미존재 시 null."""
        return await client.wiki_page_get_by_slug(slug)

    @tool
    async def wiki_pages_list(
        where: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "created_at DESC",
    ) -> list[WikiPageRead]:
        """Doc Store 의 wiki pages 리스트. where 예: {"page_type": "prd"}, {"status": "draft"}."""
        return await client.wiki_page_list(
            where=where, limit=limit, offset=offset, order_by=order_by,
        )

    @tool
    async def assignment_create(doc: AssignmentCreate) -> AssignmentRead:
        """사용자와 합의된 도메인 work item 발급 (#75 PR 4).

        **사용자와 명시적 합의 후에만 호출**. work item 후보 인식 시 먼저
        사용자에게 제목 / 범위 / 담당 agent 등을 제안하고 명시적 컨펌을 받은
        뒤 호출. 합의 없는 단계의 work item 은 row 자체로 존재하지 않음
        (Wiki / Issues 의 draft 패턴과 다름 — Assignment 는 commitment).

        status 는 'open' 으로 시작. 이후 진행 따라 assignment_update 로 갱신.
        root_session_id 는 발급된 chat session_id (있는 경우).
        """
        return await client.assignment_create(doc)

    @tool
    async def assignment_update(
        id: str, patch: AssignmentUpdate,
    ) -> AssignmentRead | None:
        """Assignment 업데이트 (UUID). status / title / metadata patch. 미존재 시 null."""
        return await client.assignment_update(UUID(id), patch)

    @tool
    async def assignment_get(id: str) -> AssignmentRead | None:
        """Assignment 조회 (UUID). 미존재 시 null."""
        return await client.assignment_get(UUID(id))

    @tool
    async def assignment_list(
        where: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "created_at DESC",
    ) -> list[AssignmentRead]:
        """Assignments 리스트. where 예: {"status": "open"}, {"owner_agent": "primary"}."""
        return await client.assignment_list(
            where=where, limit=limit, offset=offset, order_by=order_by,
        )

    @tool
    async def issues_create(doc: IssueCreate) -> IssueRead:
        """Doc Store 에 issue 생성 (Epic / Story / Task 등). type 필드로 분류."""
        return await client.issue_create(doc)

    @tool
    async def issues_update(id: str, patch: IssueUpdate) -> IssueRead | None:
        """Doc Store 의 issue 업데이트 (UUID). status patch 등. 미존재 시 null."""
        return await client.issue_update(UUID(id), patch)

    @tool
    async def issues_get(id: str) -> IssueRead | None:
        """Doc Store 의 issue 조회 (UUID). 미존재 시 null."""
        return await client.issue_get(UUID(id))

    @tool
    async def issues_list(
        where: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "created_at DESC",
    ) -> list[IssueRead]:
        """Doc Store 의 issues 리스트. where 예: {"type": "epic"}, {"status": "open"}."""
        return await client.issue_list(
            where=where, limit=limit, offset=offset, order_by=order_by,
        )

    return [
        wiki_pages_create,
        wiki_pages_update,
        wiki_pages_get,
        wiki_pages_get_by_slug,
        wiki_pages_list,
        assignment_create,
        assignment_update,
        assignment_get,
        assignment_list,
        issues_create,
        issues_update,
        issues_get,
        issues_list,
    ]


__all__ = ["build_doc_store_tools"]
