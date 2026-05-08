"""Doc Store MCP 도구명 상수 — server / client 공유 source of truth.

서버 (mcp/doc-store/tools/) 의 `@mcp.tool(name=...)` 등록과
클라이언트 (DocStoreClient) 의 호출 모두 본 상수 사용.
하드코딩된 문자열 사용 금지 — 변경 / 오타 방지 + IDE 자동완성.

#75 재설계로 chat tier (Session / Chat / Assignment) + A2A tier (5 collection)
+ 도메인 산출물 (Issue / WikiPage) 로 어휘 정렬.
"""

from __future__ import annotations

from typing import Final


# ─────────────────────────────────────────────────────────────────────────────
#  Chat tier
# ─────────────────────────────────────────────────────────────────────────────


class SessionTools:
    CREATE: Final = "session.create"
    UPDATE: Final = "session.update"
    GET: Final = "session.get"
    LIST: Final = "session.list"
    DELETE: Final = "session.delete"
    COUNT: Final = "session.count"


class ChatTools:
    """chats 는 immutable — update 미노출 (5 op + special)."""

    CREATE: Final = "chat.create"
    GET: Final = "chat.get"
    LIST: Final = "chat.list"
    DELETE: Final = "chat.delete"
    COUNT: Final = "chat.count"
    LIST_BY_SESSION: Final = "chat.list_by_session"


class AssignmentTools:
    CREATE: Final = "assignment.create"
    UPDATE: Final = "assignment.update"
    GET: Final = "assignment.get"
    LIST: Final = "assignment.list"
    DELETE: Final = "assignment.delete"
    COUNT: Final = "assignment.count"
    LIST_BY_SESSION: Final = "assignment.list_by_session"


# ─────────────────────────────────────────────────────────────────────────────
#  A2A tier
# ─────────────────────────────────────────────────────────────────────────────


class A2AContextTools:
    CREATE: Final = "a2a_context.create"
    UPDATE: Final = "a2a_context.update"
    GET: Final = "a2a_context.get"
    LIST: Final = "a2a_context.list"
    DELETE: Final = "a2a_context.delete"
    COUNT: Final = "a2a_context.count"
    FIND_BY_CONTEXT_ID: Final = "a2a_context.find_by_context_id"


class A2AMessageTools:
    """a2a_messages 는 immutable — update 미노출."""

    CREATE: Final = "a2a_message.create"
    GET: Final = "a2a_message.get"
    LIST: Final = "a2a_message.list"
    DELETE: Final = "a2a_message.delete"
    COUNT: Final = "a2a_message.count"
    LIST_BY_CONTEXT: Final = "a2a_message.list_by_context"
    LIST_BY_TASK: Final = "a2a_message.list_by_task"


class A2ATaskTools:
    CREATE: Final = "a2a_task.create"
    UPDATE: Final = "a2a_task.update"
    GET: Final = "a2a_task.get"
    LIST: Final = "a2a_task.list"
    DELETE: Final = "a2a_task.delete"
    COUNT: Final = "a2a_task.count"
    FIND_BY_TASK_ID: Final = "a2a_task.find_by_task_id"


class A2ATaskStatusUpdateTools:
    """a2a_task_status_updates 는 immutable — update 미노출."""

    CREATE: Final = "a2a_task_status_update.create"
    GET: Final = "a2a_task_status_update.get"
    LIST: Final = "a2a_task_status_update.list"
    DELETE: Final = "a2a_task_status_update.delete"
    COUNT: Final = "a2a_task_status_update.count"
    LIST_BY_TASK: Final = "a2a_task_status_update.list_by_task"


class A2ATaskArtifactTools:
    """a2a_task_artifacts 는 immutable — update 미노출."""

    CREATE: Final = "a2a_task_artifact.create"
    GET: Final = "a2a_task_artifact.get"
    LIST: Final = "a2a_task_artifact.list"
    DELETE: Final = "a2a_task_artifact.delete"
    COUNT: Final = "a2a_task_artifact.count"
    LIST_BY_TASK: Final = "a2a_task_artifact.list_by_task"


# ─────────────────────────────────────────────────────────────────────────────
#  도메인 산출물
# ─────────────────────────────────────────────────────────────────────────────


class IssueTools:
    CREATE: Final = "issue.create"
    UPDATE: Final = "issue.update"
    GET: Final = "issue.get"
    LIST: Final = "issue.list"
    DELETE: Final = "issue.delete"
    COUNT: Final = "issue.count"


class WikiPageTools:
    CREATE: Final = "wiki_page.create"
    UPDATE: Final = "wiki_page.update"
    GET: Final = "wiki_page.get"
    LIST: Final = "wiki_page.list"
    DELETE: Final = "wiki_page.delete"
    COUNT: Final = "wiki_page.count"
    GET_BY_SLUG: Final = "wiki_page.get_by_slug"


__all__ = [
    "A2AContextTools",
    "A2AMessageTools",
    "A2ATaskArtifactTools",
    "A2ATaskStatusUpdateTools",
    "A2ATaskTools",
    "AssignmentTools",
    "ChatTools",
    "IssueTools",
    "SessionTools",
    "WikiPageTools",
]
