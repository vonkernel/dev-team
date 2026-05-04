"""IssueTracker MCP 도구명 상수 — server / client 공유 source of truth.

서버 (mcp/issue-tracker/tools/) 의 `@mcp.tool(name=...)` 등록과 클라이언트
(IssueTrackerClient) 의 호출 모두 본 상수 사용. 하드코딩 문자열 사용 금지.

참고: doc-store 의 `IssueTools` 와 도구명 prefix 가 같지만 (`issue.*`) 서로
다른 MCP 서버이므로 충돌 없음. 호출자가 어느 서버로 연결됐는지가 dispatch 키.
"""

from __future__ import annotations

from typing import Final


class IssueTools:
    """이슈 CRUD + transition + close (7 op)."""

    CREATE: Final = "issue.create"
    UPDATE: Final = "issue.update"
    GET: Final = "issue.get"
    LIST: Final = "issue.list"
    CLOSE: Final = "issue.close"
    COUNT: Final = "issue.count"
    TRANSITION: Final = "issue.transition"


class StatusTools:
    """status field discover + manage (2 op)."""

    LIST: Final = "status.list"
    CREATE: Final = "status.create"


class TypeTools:
    """type field discover + manage (2 op)."""

    LIST: Final = "type.list"
    CREATE: Final = "type.create"


__all__ = ["IssueTools", "StatusTools", "TypeTools"]
