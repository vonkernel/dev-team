"""Primary 의 LangChain tool 정의 — 4 채널 통합.

Primary 는 PM 영역의 데이터 (PRD / Epic / Story / Wiki) 를 자기 도메인으로
직접 영속하고, 외부 PM 도구 (GitHub Issue / Wiki) 와 동기화하며, 정보 검색이
필요한 경우 Librarian 에 자연어 위임한다 (#63 분담 모델).

채널 4 개:

| 채널 | tool prefix | 책임 |
|---|---|---|
| Doc Store MCP | `wiki_pages_*`, `issues_*` | PM 영역 데이터 직접 write / read |
| IssueTracker MCP | `external_issue_*`, `external_status_*`, `external_type_*` | GitHub Issue 양방향 동기화 |
| Wiki MCP | `external_wiki_page_*` | GitHub Wiki 양방향 동기화 |
| Librarian A2A | `librarian_query` | 자연어 정보 검색 / 외부 리소스 조사 위임 |

각 도구는 LangChain `@tool` 로 wrap. LLM 의 `bind_tools()` 에 부착해 LLM 이
자연어 → tool 매핑 결정 (ReAct).
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID, uuid4

from dev_team_shared.a2a.client import A2AClient
from dev_team_shared.a2a.types import Message, Part, Role
from dev_team_shared.doc_store import (
    AgentTaskRead,
    DocStoreClient,
    IssueCreate as DocIssueCreate,
    IssueRead as DocIssueRead,
    IssueUpdate as DocIssueUpdate,
    WikiPageCreate as DocWikiPageCreate,
    WikiPageRead as DocWikiPageRead,
    WikiPageUpdate as DocWikiPageUpdate,
)
from dev_team_shared.issue_tracker import (
    IssueCreate as ExtIssueCreate,
    IssueRead as ExtIssueRead,
    IssueTrackerClient,
    IssueUpdate as ExtIssueUpdate,
    StatusRef,
    TypeRef,
)
from dev_team_shared.wiki import (
    PageCreate as ExtPageCreate,
    PageRead as ExtPageRead,
    PageRef as ExtPageRef,
    PageUpdate as ExtPageUpdate,
    WikiClient,
)
from langchain_core.tools import BaseTool, tool


def build_tools(
    *,
    doc_store: DocStoreClient,
    issue_tracker: IssueTrackerClient | None,
    wiki: WikiClient | None,
    librarian: A2AClient | None,
) -> list[BaseTool]:
    """4 채널 클라이언트를 받아 LangChain tool 목록 반환.

    - `doc_store` 는 필수 (Primary 의 자기 도메인 영속).
    - `issue_tracker` / `wiki` / `librarian` 은 선택 — 미주입 시 해당 채널 도구
      미노출. 본격 sync / read 위임 활성화 시 wiring (env 변수로 활성).
    """
    tools: list[BaseTool] = []

    # ──────────────────────────────────────────────────────────────────
    # Doc Store MCP — PM 자기 도메인 (wiki_pages + issues)
    # ──────────────────────────────────────────────────────────────────

    @tool
    async def wiki_pages_create(doc: DocWikiPageCreate) -> DocWikiPageRead:
        """Doc Store 에 wiki page 생성 (PRD / ADR / business_rule 등). page_type 필드로 분류."""
        return await doc_store.wiki_page_create(doc)

    @tool
    async def wiki_pages_update(id: str, patch: DocWikiPageUpdate) -> DocWikiPageRead | None:
        """Doc Store 의 wiki page 업데이트 (UUID). status patch 등에 사용. 미존재 시 null."""
        return await doc_store.wiki_page_update(UUID(id), patch)

    @tool
    async def wiki_pages_get(id: str) -> DocWikiPageRead | None:
        """Doc Store 의 wiki page 조회 (UUID). 미존재 시 null."""
        return await doc_store.wiki_page_get(UUID(id))

    @tool
    async def wiki_pages_get_by_slug(slug: str) -> DocWikiPageRead | None:
        """Doc Store 의 wiki page 를 slug 로 조회 (예: 'prd-guestbook'). 미존재 시 null."""
        return await doc_store.wiki_page_get_by_slug(slug)

    @tool
    async def wiki_pages_list(
        where: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "created_at DESC",
    ) -> list[DocWikiPageRead]:
        """Doc Store 의 wiki pages 리스트. where 예: {"page_type": "prd"}, {"status": "draft"}."""
        return await doc_store.wiki_page_list(
            where=where, limit=limit, offset=offset, order_by=order_by,
        )

    @tool
    async def issues_create(doc: DocIssueCreate) -> DocIssueRead:
        """Doc Store 에 issue 생성 (Epic / Story / Task 등). type 필드로 분류."""
        return await doc_store.issue_create(doc)

    @tool
    async def issues_update(id: str, patch: DocIssueUpdate) -> DocIssueRead | None:
        """Doc Store 의 issue 업데이트 (UUID). status patch 등. 미존재 시 null."""
        return await doc_store.issue_update(UUID(id), patch)

    @tool
    async def issues_get(id: str) -> DocIssueRead | None:
        """Doc Store 의 issue 조회 (UUID). 미존재 시 null."""
        return await doc_store.issue_get(UUID(id))

    @tool
    async def issues_list(
        where: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "created_at DESC",
    ) -> list[DocIssueRead]:
        """Doc Store 의 issues 리스트. where 예: {"type": "epic"}, {"status": "open"}."""
        return await doc_store.issue_list(
            where=where, limit=limit, offset=offset, order_by=order_by,
        )

    # 자기 영속 데이터의 chronicler 로그 / 작업 메타도 직접 read 가능.
    @tool
    async def agent_tasks_get(id: str) -> AgentTaskRead | None:
        """Doc Store 의 agent_task 조회 (UUID). Chronicler 가 영속한 작업 메타. 미존재 시 null."""
        return await doc_store.agent_task_get(UUID(id))

    @tool
    async def agent_tasks_list(
        where: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "created_at DESC",
    ) -> list[AgentTaskRead]:
        """Doc Store 의 agent_tasks 리스트."""
        return await doc_store.agent_task_list(
            where=where, limit=limit, offset=offset, order_by=order_by,
        )

    tools += [
        wiki_pages_create,
        wiki_pages_update,
        wiki_pages_get,
        wiki_pages_get_by_slug,
        wiki_pages_list,
        issues_create,
        issues_update,
        issues_get,
        issues_list,
        agent_tasks_get,
        agent_tasks_list,
    ]

    # ──────────────────────────────────────────────────────────────────
    # IssueTracker MCP — 외부 GitHub Issue sync
    # ──────────────────────────────────────────────────────────────────

    if issue_tracker is not None:

        @tool
        async def external_issue_create(doc: ExtIssueCreate) -> ExtIssueRead:
            """외부 IssueTracker (GitHub Issue) 에 이슈 생성. Doc Store 의 issue 와 sync 시점에 호출."""
            return await issue_tracker.issues.create(doc)

        @tool
        async def external_issue_update(
            id_or_number: str, patch: ExtIssueUpdate,
        ) -> ExtIssueRead | None:
            """외부 IssueTracker 의 이슈 업데이트 (id 또는 number). status / labels 등 patch."""
            return await issue_tracker.issues.update(id_or_number, patch)

        @tool
        async def external_issue_list(
            where: dict[str, Any] | None = None,
            limit: int = 100,
        ) -> list[ExtIssueRead]:
            """외부 IssueTracker 이슈 리스트. where 는 backend 별 필터 (state / label 등)."""
            return await issue_tracker.issues.list(where=where, limit=limit)

        @tool
        async def external_status_list() -> list[StatusRef]:
            """외부 IssueTracker 의 status 목록 동적 조회. LLM 이 의미적 매핑 결정에 사용."""
            return await issue_tracker.statuses.list()

        @tool
        async def external_status_create(name: str) -> StatusRef:
            """외부 IssueTracker 에 새 status 생성 (현 컨텍스트에 부족할 때)."""
            return await issue_tracker.statuses.create(name)

        @tool
        async def external_type_list() -> list[TypeRef]:
            """외부 IssueTracker 의 type 목록 동적 조회 (Epic / Story / Task 등)."""
            return await issue_tracker.types.list()

        @tool
        async def external_type_create(name: str) -> TypeRef:
            """외부 IssueTracker 에 새 type 생성."""
            return await issue_tracker.types.create(name)

        tools += [
            external_issue_create,
            external_issue_update,
            external_issue_list,
            external_status_list,
            external_status_create,
            external_type_list,
            external_type_create,
        ]

    # ──────────────────────────────────────────────────────────────────
    # Wiki MCP — 외부 GitHub Wiki sync
    # ──────────────────────────────────────────────────────────────────

    if wiki is not None:

        @tool
        async def external_wiki_page_create(doc: ExtPageCreate) -> ExtPageRead:
            """외부 Wiki (GitHub Wiki) 에 페이지 생성. Doc Store 의 wiki_pages 와 sync."""
            return await wiki.pages.create(doc)

        @tool
        async def external_wiki_page_update(
            slug: str, patch: ExtPageUpdate,
        ) -> ExtPageRead | None:
            """외부 Wiki 페이지 업데이트 (slug)."""
            return await wiki.pages.update(slug, patch)

        @tool
        async def external_wiki_page_get(slug: str) -> ExtPageRead | None:
            """외부 Wiki 페이지 조회 (slug). 미존재 시 null."""
            return await wiki.pages.get(slug)

        @tool
        async def external_wiki_page_list() -> list[ExtPageRef]:
            """외부 Wiki 페이지 리스트 (slug + title 등 ref 만 반환). 본문은 get(slug) 으로."""
            return await wiki.pages.list()

        tools += [
            external_wiki_page_create,
            external_wiki_page_update,
            external_wiki_page_get,
            external_wiki_page_list,
        ]

    # ──────────────────────────────────────────────────────────────────
    # Librarian A2A — 자연어 정보 검색 / 외부 리소스 조사 위임
    # ──────────────────────────────────────────────────────────────────

    if librarian is not None:

        @tool
        async def librarian_query(query: str) -> str:
            """Librarian (사서) 에 자연어로 정보 검색 / 외부 리소스 조사 위임.

            사용 시점:
            - Doc Store 의 자연어 / 교차 컬렉션 쿼리 (예: "context X 의 대화 로그")
            - 라이브러리 / 프레임워크 docs (context7)
            - 사용자 제공 URL 페이지 (mcp/web-fetch)
            - 일반 web 검색 (Claude Web Search)

            자기 도메인의 단순 read (식별자 알 때) 는 wiki_pages_* / issues_*
            를 직접 호출하는 게 더 효율적. Librarian 은 자연어 / 교차 / 외부 조사
            전용.
            """
            message = Message(
                message_id=str(uuid4()),
                role=Role.USER,
                parts=[Part(text=query)],
                context_id=str(uuid4()),
            )
            # A2AClient 는 sync — async tool 안에서 호출 시 thread offload.
            result = await asyncio.to_thread(librarian.send_message, message)
            return _extract_response_text(result)

        tools += [librarian_query]

    return tools


def _extract_response_text(result: dict[str, Any]) -> str:
    """A2A SendMessage 응답 (Task 또는 Message) 에서 자연어 텍스트 추출.

    응답 형태:
    - Message: `parts: [{text: "..."}]` 직접 반환
    - Task: `status.message.parts[].text` 또는 `artifacts[].parts[].text`

    LLM 에게 그대로 전달할 자연어 응답 문자열.
    """
    # Direct Message
    parts = result.get("parts") or []
    pieces: list[str] = []
    for p in parts:
        t = p.get("text")
        if t:
            pieces.append(t)
    # Task — status message
    status = result.get("status") or {}
    status_msg = status.get("message") or {}
    for p in status_msg.get("parts") or []:
        t = p.get("text")
        if t:
            pieces.append(t)
    # Task — artifacts
    for art in result.get("artifacts") or []:
        for p in art.get("parts") or []:
            t = p.get("text")
            if t:
                pieces.append(t)
    return "".join(pieces) or "(no response)"


__all__ = ["build_tools"]
