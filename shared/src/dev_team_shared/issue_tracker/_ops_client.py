"""IssueTrackerClient 의 도메인별 sub-client 들.

ISP 적용 — 호출자 (P 등) 가 좁은 인터페이스에 의존:

    client = IssueTrackerClient(mcp)
    issues: IssueClient = client.issues   # issue 작업만 할 때
    statuses: StatusClient = client.statuses

각 sub-client 는 같은 `_Invoker` 를 공유 (MCP 도구 호출 + structuredContent 풀이).
"""

from __future__ import annotations

from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

from dev_team_shared.issue_tracker.schemas import (
    FieldRef,
    IssueCreate,
    IssueRead,
    IssueUpdate,
    StatusRef,
    TypeRef,
)
from dev_team_shared.issue_tracker.tool_names import (
    FieldTools,
    IssueTools,
    StatusTools,
    TypeTools,
)

T = TypeVar("T", bound=BaseModel)


class _Invoker(Protocol):
    """sub-client 공유 인터페이스 — MCP 도구 호출 + structuredContent 추출."""

    async def call(
        self, name: str, args: dict[str, Any], return_type: type[T],
    ) -> T: ...

    async def call_optional(
        self, name: str, args: dict[str, Any], return_type: type[T],
    ) -> T | None: ...

    async def call_list(
        self, name: str, args: dict[str, Any], item_type: type[T],
    ) -> list[T]: ...

    async def call_scalar(self, name: str, args: dict[str, Any]) -> Any: ...


class IssueClient:
    """이슈 lifecycle (8 op)."""

    def __init__(self, invoker: _Invoker) -> None:
        self._invoker = invoker

    async def create(self, doc: IssueCreate) -> IssueRead:
        return await self._invoker.call(
            IssueTools.CREATE, {"doc": doc.model_dump(mode="json")}, IssueRead,
        )

    async def update(self, ref: str, patch: IssueUpdate) -> IssueRead | None:
        return await self._invoker.call_optional(
            IssueTools.UPDATE,
            {"ref": ref, "patch": patch.model_dump(mode="json", exclude_unset=True)},
            IssueRead,
        )

    async def get(self, ref: str) -> IssueRead | None:
        return await self._invoker.call_optional(
            IssueTools.GET, {"ref": ref}, IssueRead,
        )

    async def list(
        self,
        *,
        where: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "created_at desc",
    ) -> list[IssueRead]:
        args: dict[str, Any] = {
            "limit": limit, "offset": offset, "order_by": order_by,
        }
        if where is not None:
            args["where"] = where
        return await self._invoker.call_list(IssueTools.LIST, args, IssueRead)

    async def close(self, ref: str) -> bool:
        return await self._invoker.call_scalar(IssueTools.CLOSE, {"ref": ref})

    async def delete(self, ref: str) -> bool:
        return await self._invoker.call_scalar(IssueTools.DELETE, {"ref": ref})

    async def count(self, *, where: dict[str, Any] | None = None) -> int:
        args: dict[str, Any] = {} if where is None else {"where": where}
        return await self._invoker.call_scalar(IssueTools.COUNT, args)

    async def transition(self, ref: str, status_id: str) -> None:
        await self._invoker.call_scalar(
            IssueTools.TRANSITION, {"ref": ref, "status_id": status_id},
        )


class StatusClient:
    """status field 메타데이터 (3 op)."""

    def __init__(self, invoker: _Invoker) -> None:
        self._invoker = invoker

    async def list(self) -> list[StatusRef]:
        return await self._invoker.call_list(StatusTools.LIST, {}, StatusRef)

    async def create(self, name: str) -> StatusRef:
        return await self._invoker.call(
            StatusTools.CREATE, {"name": name}, StatusRef,
        )

    async def delete(self, status_id: str) -> bool:
        return await self._invoker.call_scalar(
            StatusTools.DELETE, {"status_id": status_id},
        )


class TypeClient:
    """type field 메타데이터 (3 op)."""

    def __init__(self, invoker: _Invoker) -> None:
        self._invoker = invoker

    async def list(self) -> list[TypeRef]:
        return await self._invoker.call_list(TypeTools.LIST, {}, TypeRef)

    async def create(self, name: str) -> TypeRef:
        return await self._invoker.call(TypeTools.CREATE, {"name": name}, TypeRef)

    async def delete(self, type_id: str) -> bool:
        return await self._invoker.call_scalar(
            TypeTools.DELETE, {"type_id": type_id},
        )


class FieldClient:
    """board field 자체 (3 op)."""

    def __init__(self, invoker: _Invoker) -> None:
        self._invoker = invoker

    async def list(self) -> list[FieldRef]:
        return await self._invoker.call_list(FieldTools.LIST, {}, FieldRef)

    async def create(self, name: str, kind: str = "single_select") -> FieldRef:
        return await self._invoker.call(
            FieldTools.CREATE, {"name": name, "kind": kind}, FieldRef,
        )

    async def delete(self, field_id: str) -> bool:
        return await self._invoker.call_scalar(
            FieldTools.DELETE, {"field_id": field_id},
        )


__all__ = [
    "FieldClient",
    "IssueClient",
    "StatusClient",
    "TypeClient",
    "_Invoker",
]
