"""Doc Store MCP 채널 LangChain tools.

Primary 자기 도메인 (PRD / Epic / Story / Wiki + Assignment) 의 직접 write /
read. #75 재설계로 agent_tasks 가 assignments 로 재정의됨.

Assignment 의 명시 발급 / 관리는 chat protocol 도입 (PR 4) 시점에 추가될
예정. PR 1 단계에선 Doc Store 9 op (wiki_pages 5 + issues 4) 만 노출.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from dev_team_shared.doc_store import (
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
        issues_create,
        issues_update,
        issues_get,
        issues_list,
    ]


__all__ = ["build_doc_store_tools"]
