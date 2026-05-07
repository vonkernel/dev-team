"""Librarian 의 LangChain tool 정의.

Doc Store 의 5 collection read 도구 + 조합 쿼리 1 개. LangChain `@tool` 로
wrapping 해 LLM 의 `bind_tools()` 에 부착 — LLM 이 자연어 → tool 매핑 결정.

도메인 wrapper (`upsert_prd` 등) 박지 않음 (root CLAUDE.md "에이전트 ↔ 외부
도구 운영 원칙"). LLM 이 매 요청 컨텍스트에 맞춰 page_type / type 필드 결정.

분담 모델 (#63 정정 — 2026-05): write 는 각 에이전트가 Doc Store / Atlas
MCP 직접. **Librarian 은 read-only 사서** — 자연어 / 교차 쿼리 매핑.

M3 노출 op (read 13 + 조합 1 = 14):
- wiki_pages: get / get_by_slug / list
- issues: get / list
- agent_tasks: get / list
- agent_sessions: get / list / list_by_task / find_by_context
- agent_items: list / list_by_session
- 조합: chronicler_log_by_context (session find + items list 결합)
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from dev_team_shared.doc_store import (
    AgentItemRead,
    AgentSessionRead,
    AgentTaskRead,
    DocStoreClient,
    IssueRead,
    WikiPageRead,
)
from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, ConfigDict


class ChroniclerLog(BaseModel):
    """contextId 1 개의 chronicler 로그 = session + items 결합 결과."""

    model_config = ConfigDict(extra="forbid")

    session: AgentSessionRead | None
    items: list[AgentItemRead]


def build_tools(client: DocStoreClient) -> list[BaseTool]:
    """DocStoreClient 클로저 캡처 → LangChain tool 목록 반환.

    server.lifespan 에서 client 생성 후 호출. 결과를 LLM `bind_tools()` 에 부착.
    """

    # ──────────────────────────────────────────────────────────────────
    # wiki_pages (read)
    # ──────────────────────────────────────────────────────────────────

    @tool
    async def wiki_pages_get(id: str) -> WikiPageRead | None:
        """Get wiki page by id (UUID). 미존재 시 null."""
        return await client.wiki_page_get(UUID(id))

    @tool
    async def wiki_pages_get_by_slug(slug: str) -> WikiPageRead | None:
        """Get wiki page by slug (예: 'prd-guestbook'). 미존재 시 null."""
        return await client.wiki_page_get_by_slug(slug)

    @tool
    async def wiki_pages_list(
        where: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "created_at DESC",
    ) -> list[WikiPageRead]:
        """List wiki pages. where 는 단순 equality 필터 (예: {"page_type": "prd"})."""
        return await client.wiki_page_list(
            where=where, limit=limit, offset=offset, order_by=order_by,
        )

    # ──────────────────────────────────────────────────────────────────
    # issues (read)
    # ──────────────────────────────────────────────────────────────────

    @tool
    async def issues_get(id: str) -> IssueRead | None:
        """Get issue by id (UUID). 미존재 시 null."""
        return await client.issue_get(UUID(id))

    @tool
    async def issues_list(
        where: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "created_at DESC",
    ) -> list[IssueRead]:
        """List issues. where 예: {"type": "epic"} or {"status": "open"}."""
        return await client.issue_list(
            where=where, limit=limit, offset=offset, order_by=order_by,
        )

    # ──────────────────────────────────────────────────────────────────
    # agent_tasks (read)
    # ──────────────────────────────────────────────────────────────────

    @tool
    async def agent_tasks_get(id: str) -> AgentTaskRead | None:
        """Get agent_task by id (UUID). 미존재 시 null."""
        return await client.agent_task_get(UUID(id))

    @tool
    async def agent_tasks_list(
        where: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "created_at DESC",
    ) -> list[AgentTaskRead]:
        """List agent tasks. Chronicler 가 영속한 작업 단위 메타."""
        return await client.agent_task_list(
            where=where, limit=limit, offset=offset, order_by=order_by,
        )

    # ──────────────────────────────────────────────────────────────────
    # agent_sessions (read)
    # ──────────────────────────────────────────────────────────────────

    @tool
    async def agent_sessions_get(id: str) -> AgentSessionRead | None:
        """Get agent_session by id (UUID). 미존재 시 null."""
        return await client.agent_session_get(UUID(id))

    @tool
    async def agent_sessions_list(
        where: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "started_at DESC",
    ) -> list[AgentSessionRead]:
        """List agent sessions (대화 흐름)."""
        return await client.agent_session_list(
            where=where, limit=limit, offset=offset, order_by=order_by,
        )

    @tool
    async def agent_sessions_list_by_task(task_id: str) -> list[AgentSessionRead]:
        """List sessions for a task (UUID)."""
        return await client.agent_session_list_by_task(UUID(task_id))

    @tool
    async def agent_sessions_find_by_context(context_id: str) -> AgentSessionRead | None:
        """contextId 로 session 1개 lookup. 미존재 시 null. chronicler 로그 entry."""
        return await client.agent_session_find_by_context(context_id)

    # ──────────────────────────────────────────────────────────────────
    # agent_items (read)
    # ──────────────────────────────────────────────────────────────────

    @tool
    async def agent_items_list(
        where: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "created_at ASC",
    ) -> list[AgentItemRead]:
        """List agent items (메시지)."""
        return await client.agent_item_list(
            where=where, limit=limit, offset=offset, order_by=order_by,
        )

    @tool
    async def agent_items_list_by_session(session_id: str) -> list[AgentItemRead]:
        """List items for a session (UUID). chronicler 로그 본문."""
        return await client.agent_item_list_by_session(UUID(session_id))

    # ──────────────────────────────────────────────────────────────────
    # 조합 쿼리 (composite read)
    # ──────────────────────────────────────────────────────────────────

    @tool
    async def chronicler_log_by_context(context_id: str) -> ChroniclerLog:
        """contextId 의 chronicler 로그 (session + items) 한 번에 조회.

        `agent_sessions_find_by_context` + `agent_items_list_by_session` 두
        호출을 합친 조합 쿼리. session 미존재 시 items 는 빈 리스트.
        """
        session = await client.agent_session_find_by_context(context_id)
        if session is None:
            return ChroniclerLog(session=None, items=[])
        items = await client.agent_item_list_by_session(session.id)
        return ChroniclerLog(session=session, items=items)

    return [
        wiki_pages_get,
        wiki_pages_get_by_slug,
        wiki_pages_list,
        issues_get,
        issues_list,
        agent_tasks_get,
        agent_tasks_list,
        agent_sessions_get,
        agent_sessions_list,
        agent_sessions_list_by_task,
        agent_sessions_find_by_context,
        agent_items_list,
        agent_items_list_by_session,
        chronicler_log_by_context,
    ]


__all__ = ["build_tools", "ChroniclerLog"]
