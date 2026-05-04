"""IssueTrackerClient — IssueTracker MCP 의 typed 클라이언트.

ISP / composition: 책임별 sub-client 4 개를 노출 (`issues / statuses / types /
fields`). 호출자는 좁은 인터페이스에 의존 가능.

사용:

    async with await StreamableMCPClient.connect(url) as mcp:
        client = IssueTrackerClient(mcp)
        statuses = await client.statuses.list()
        new_st = await client.statuses.create("Security Review")
        issue = await client.issues.create(IssueCreate(...))
        await client.issues.transition(issue.ref, status_id=new_st.id)

    # ISP — issue 작업만 할 때
    issues_only = client.issues   # IssueClient
"""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

from dev_team_shared.issue_tracker._ops_client import (
    FieldClient,
    IssueClient,
    StatusClient,
    TypeClient,
)
from dev_team_shared.mcp_client import StreamableMCPClient

T = TypeVar("T", bound=BaseModel)


class IssueTrackerClient:
    """4 sub-client 의 컴포지트. 외부 진입점."""

    def __init__(self, mcp: StreamableMCPClient) -> None:
        self._mcp = mcp
        invoker = _MCPInvoker(mcp)
        self._issues = IssueClient(invoker)
        self._statuses = StatusClient(invoker)
        self._types = TypeClient(invoker)
        self._fields = FieldClient(invoker)

    @property
    def issues(self) -> IssueClient:
        return self._issues

    @property
    def statuses(self) -> StatusClient:
        return self._statuses

    @property
    def types(self) -> TypeClient:
        return self._types

    @property
    def fields(self) -> FieldClient:
        return self._fields


class _MCPInvoker:
    """Sub-client 들이 공유하는 호출 헬퍼 — FastMCP structuredContent 규약 흡수.

    FastMCP 응답 형태:
    - Pydantic 모델 단건 → 모델 dict 그대로 (unwrapped)
    - Optional[Model] / list / scalar → `{"result": <value>}` 로 wrap
    """

    def __init__(self, mcp: StreamableMCPClient) -> None:
        self._mcp = mcp

    async def call(
        self, name: str, args: dict[str, Any], return_type: type[T],
    ) -> T:
        sc = await self._invoke(name, args)
        return return_type.model_validate(sc)

    async def call_optional(
        self, name: str, args: dict[str, Any], return_type: type[T],
    ) -> T | None:
        sc = await self._invoke(name, args)
        inner = sc.get("result")
        if inner is None:
            return None
        return return_type.model_validate(inner)

    async def call_list(
        self, name: str, args: dict[str, Any], item_type: type[T],
    ) -> list[T]:
        sc = await self._invoke(name, args)
        items = sc.get("result") or []
        return [item_type.model_validate(it) for it in items]

    async def call_scalar(self, name: str, args: dict[str, Any]) -> Any:
        sc = await self._invoke(name, args)
        return sc.get("result")

    async def _invoke(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        result = await self._mcp.call_tool(name, args)
        return result.structuredContent or {}


__all__ = ["IssueTrackerClient"]
