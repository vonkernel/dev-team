"""Document DB MCP 도구명 상수 — server / client 공유 source of truth.

서버 (mcp/document-db/tools/) 의 `@mcp.tool(name=...)` 등록과
클라이언트 (DocumentDbClient) 의 호출 모두 본 상수 사용.
하드코딩된 문자열 사용 금지 — 변경 / 오타 방지 + IDE 자동완성.
"""

from __future__ import annotations

from typing import Final


class AgentTaskTools:
    CREATE: Final = "agent_task.create"
    UPDATE: Final = "agent_task.update"
    GET: Final = "agent_task.get"
    LIST: Final = "agent_task.list"
    DELETE: Final = "agent_task.delete"
    COUNT: Final = "agent_task.count"


class AgentSessionTools:
    CREATE: Final = "agent_session.create"
    UPDATE: Final = "agent_session.update"
    GET: Final = "agent_session.get"
    LIST: Final = "agent_session.list"
    DELETE: Final = "agent_session.delete"
    COUNT: Final = "agent_session.count"
    LIST_BY_TASK: Final = "agent_session.list_by_task"
    FIND_BY_CONTEXT: Final = "agent_session.find_by_context"


class AgentItemTools:
    CREATE: Final = "agent_item.create"   # immutable — no update
    GET: Final = "agent_item.get"
    LIST: Final = "agent_item.list"
    DELETE: Final = "agent_item.delete"
    COUNT: Final = "agent_item.count"
    LIST_BY_SESSION: Final = "agent_item.list_by_session"


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
    "AgentItemTools",
    "AgentSessionTools",
    "AgentTaskTools",
    "IssueTools",
    "WikiPageTools",
]
