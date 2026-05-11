"""Librarian 의 LangChain tool 정의.

Doc Store collection 의 read 도구 + 조합 쿼리. LangChain `@tool` 로 wrapping
해 LLM 의 `bind_tools()` 에 부착 — LLM 이 자연어 → tool 매핑 결정.

도메인 wrapper (`upsert_prd` 등) 박지 않음 (root CLAUDE.md "에이전트 ↔ 외부
도구 운영 원칙"). LLM 이 매 요청 컨텍스트에 맞춰 page_type / type 필드 결정.

분담 모델 (#63): write 는 각 에이전트가 Doc Store / Atlas MCP 직접.
**Librarian 은 read-only 사서** — 자연어 / 교차 쿼리 매핑.

#75 재설계: chat tier (sessions / chats / assignments) + A2A tier
(a2a_contexts / a2a_messages / a2a_tasks / a2a_task_status_updates /
a2a_task_artifacts) + 도메인 산출물 (issues / wiki_pages) 의 read 도구 노출.
조합 쿼리는 PR 2 (Chronicler 재작성 + chat protocol 도입) 후 새 그루핑 단위
(session, assignment) 기반으로 추가.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from dev_team_shared.doc_store import (
    A2AContextRead,
    A2AMessageRead,
    A2ATaskArtifactRead,
    A2ATaskRead,
    A2ATaskStatusUpdateRead,
    AssignmentRead,
    ChatRead,
    DocStoreClient,
    IssueRead,
    SessionRead,
    WikiPageRead,
)
from langchain_core.tools import BaseTool, tool


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
    # assignments (도메인 work item) — read
    # ──────────────────────────────────────────────────────────────────

    @tool
    async def assignments_get(id: str) -> AssignmentRead | None:
        """Get assignment by id (UUID). 미존재 시 null."""
        return await client.assignment_get(UUID(id))

    @tool
    async def assignments_list(
        where: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "created_at DESC",
    ) -> list[AssignmentRead]:
        """List assignments. where 예: {"status": "open"} or {"owner_agent": "primary"}."""
        return await client.assignment_list(
            where=where, limit=limit, offset=offset, order_by=order_by,
        )

    @tool
    async def assignments_list_by_session(root_session_id: str) -> list[AssignmentRead]:
        """List assignments derived from a chat session (UUID)."""
        return await client.assignment_list_by_session(UUID(root_session_id))

    # ──────────────────────────────────────────────────────────────────
    # sessions (chat tier) — read
    # ──────────────────────────────────────────────────────────────────

    @tool
    async def sessions_get(id: str) -> SessionRead | None:
        """Get chat session by id (UUID). 미존재 시 null."""
        return await client.session_get(UUID(id))

    @tool
    async def sessions_list(
        where: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "started_at DESC",
    ) -> list[SessionRead]:
        """List chat sessions (UG↔P/A 대화창)."""
        return await client.session_list(
            where=where, limit=limit, offset=offset, order_by=order_by,
        )

    # ──────────────────────────────────────────────────────────────────
    # chats (chat tier) — read
    # ──────────────────────────────────────────────────────────────────

    @tool
    async def chats_list_by_session(session_id: str) -> list[ChatRead]:
        """List chats (메시지) within a session (UUID), ordered by created_at."""
        return await client.chat_list_by_session(UUID(session_id))

    # ──────────────────────────────────────────────────────────────────
    # a2a_contexts (A2A tier) — read
    # ──────────────────────────────────────────────────────────────────

    @tool
    async def a2a_contexts_get(id: str) -> A2AContextRead | None:
        """Get a2a_context by id (UUID). 미존재 시 null."""
        return await client.a2a_context_get(UUID(id))

    @tool
    async def a2a_contexts_list(
        where: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "started_at DESC",
    ) -> list[A2AContextRead]:
        """List a2a_contexts. where 예: {"trace_id": "..."}."""
        return await client.a2a_context_list(
            where=where, limit=limit, offset=offset, order_by=order_by,
        )

    # a2a_contexts_find_by_context_id 폐기 (#75 PR 4) — wire context_id
    # 컬럼 자체 폐기. a2a_contexts_get(id) 직접 사용.

    # ──────────────────────────────────────────────────────────────────
    # a2a_messages (A2A tier) — read
    # ──────────────────────────────────────────────────────────────────

    @tool
    async def a2a_messages_list_by_context(a2a_context_id: str) -> list[A2AMessageRead]:
        """List messages within an a2a_context (UUID)."""
        return await client.a2a_message_list_by_context(UUID(a2a_context_id))

    @tool
    async def a2a_messages_list_by_task(a2a_task_id: str) -> list[A2AMessageRead]:
        """List Task.history messages of an a2a_task (UUID)."""
        return await client.a2a_message_list_by_task(UUID(a2a_task_id))

    # ──────────────────────────────────────────────────────────────────
    # a2a_tasks (A2A tier) — read
    # ──────────────────────────────────────────────────────────────────

    @tool
    async def a2a_tasks_get(id: str) -> A2ATaskRead | None:
        """Get a2a_task by id (UUID). 미존재 시 null."""
        return await client.a2a_task_get(UUID(id))

    @tool
    async def a2a_tasks_list(
        where: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "submitted_at DESC",
    ) -> list[A2ATaskRead]:
        """List a2a_tasks. where 예: {"state": "WORKING"}."""
        return await client.a2a_task_list(
            where=where, limit=limit, offset=offset, order_by=order_by,
        )

    # a2a_tasks_find_by_task_id 폐기 (#75 PR 4) — wire task_id 컬럼 자체 폐기.
    # a2a_tasks_get(id) 직접 사용.

    # ──────────────────────────────────────────────────────────────────
    # a2a_task_status_updates / a2a_task_artifacts (A2A tier) — read
    # ──────────────────────────────────────────────────────────────────

    @tool
    async def a2a_task_status_updates_list_by_task(
        a2a_task_id: str,
    ) -> list[A2ATaskStatusUpdateRead]:
        """List state transitions of an a2a_task (UUID), ordered by transitioned_at."""
        return await client.a2a_task_status_update_list_by_task(UUID(a2a_task_id))

    @tool
    async def a2a_task_artifacts_list_by_task(
        a2a_task_id: str,
    ) -> list[A2ATaskArtifactRead]:
        """List artifacts of an a2a_task (UUID), ordered by created_at."""
        return await client.a2a_task_artifact_list_by_task(UUID(a2a_task_id))

    return [
        # 도메인 산출물
        wiki_pages_get,
        wiki_pages_get_by_slug,
        wiki_pages_list,
        issues_get,
        issues_list,
        # chat tier
        assignments_get,
        assignments_list,
        assignments_list_by_session,
        sessions_get,
        sessions_list,
        chats_list_by_session,
        # a2a tier
        a2a_contexts_get,
        a2a_contexts_list,
        a2a_messages_list_by_context,
        a2a_messages_list_by_task,
        a2a_tasks_get,
        a2a_tasks_list,
        a2a_task_status_updates_list_by_task,
        a2a_task_artifacts_list_by_task,
    ]


__all__ = ["build_tools"]
