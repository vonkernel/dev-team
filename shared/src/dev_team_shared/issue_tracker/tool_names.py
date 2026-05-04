"""IssueTracker MCP 도구명 상수 — server / client 공유 source of truth.

서버 (mcp/issue-tracker/tools/) 의 `@mcp.tool(name=...)` 등록과 클라이언트
(IssueTrackerClient) 의 호출 모두 본 상수 사용. 하드코딩 문자열 사용 금지.

참고: doc-store 의 `IssueTools` 와 도구명 prefix 가 같지만 (`issue.*`) 서로
다른 MCP 서버이므로 충돌 없음. 호출자가 어느 서버로 연결됐는지가 dispatch 키.
"""

from __future__ import annotations

from typing import Final


class IssueTools:
    """이슈 CRUD + lifecycle (8 op).

    `close` 는 가벼운 종료 (보존), `delete` 는 영구 삭제 (admin 권한 필요).
    """

    CREATE: Final = "issue.create"
    UPDATE: Final = "issue.update"
    GET: Final = "issue.get"
    LIST: Final = "issue.list"
    CLOSE: Final = "issue.close"
    DELETE: Final = "issue.delete"
    COUNT: Final = "issue.count"
    TRANSITION: Final = "issue.transition"


class StatusTools:
    """status field discover + manage (3 op)."""

    LIST: Final = "status.list"
    CREATE: Final = "status.create"
    DELETE: Final = "status.delete"


class TypeTools:
    """type field discover + manage (3 op)."""

    LIST: Final = "type.list"
    CREATE: Final = "type.create"
    DELETE: Final = "type.delete"


class FieldTools:
    """board field discover + manage (3 op).

    P 가 board 에 어떤 field 가 있는지 조회 + 부족하면 직접 추가 / 정리.
    PM 워크플로우의 setup 단계.
    """

    LIST: Final = "field.list"
    CREATE: Final = "field.create"
    DELETE: Final = "field.delete"


__all__ = ["FieldTools", "IssueTools", "StatusTools", "TypeTools"]
