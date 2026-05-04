"""IssueTrackerClient — IssueTracker MCP 의 typed 클라이언트.

호출자는 Pydantic 모델 입출력만 다룸. wire-level 디테일 (도구명 / dict 래핑 /
JSON parse) 모두 본 클래스 안에 격리.

사용:

    async with StreamableMCPClient.connect(url) as mcp:
        tracker = IssueTrackerClient(mcp)
        statuses = await tracker.status_list()              # → list[StatusRef]
        new_st = await tracker.status_create("Security Review")
        issue = await tracker.issue_create(IssueCreate(...))
        await tracker.issue_transition(issue.ref, status_id=new_st.id)
"""

from __future__ import annotations

from typing import Any, TypeVar

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
from dev_team_shared.mcp_client import StreamableMCPClient

T = TypeVar("T", bound=BaseModel)


class IssueTrackerClient:
    """Typed wrapper around `StreamableMCPClient` for IssueTracker MCP 도구."""

    def __init__(self, mcp: StreamableMCPClient) -> None:
        self._mcp = mcp

    # ──────────────────────────────────────────────────────────────────
    # field — board 구조 discover + manage (PM 워크플로우 setup 단계)
    # ──────────────────────────────────────────────────────────────────

    async def field_list(self) -> list[FieldRef]:
        return await self._call_list(FieldTools.LIST, {}, FieldRef)

    async def field_create(self, name: str, kind: str = "single_select") -> FieldRef:
        return await self._call(
            FieldTools.CREATE, {"name": name, "kind": kind}, FieldRef,
        )

    async def field_delete(self, field_id: str) -> bool:
        return await self._call_scalar(FieldTools.DELETE, {"field_id": field_id})

    # ──────────────────────────────────────────────────────────────────
    # status — 도구 메타데이터 discover + manage
    # ──────────────────────────────────────────────────────────────────

    async def status_list(self) -> list[StatusRef]:
        return await self._call_list(StatusTools.LIST, {}, StatusRef)

    async def status_create(self, name: str) -> StatusRef:
        return await self._call(StatusTools.CREATE, {"name": name}, StatusRef)

    async def status_delete(self, status_id: str) -> bool:
        return await self._call_scalar(
            StatusTools.DELETE, {"status_id": status_id},
        )

    # ──────────────────────────────────────────────────────────────────
    # type
    # ──────────────────────────────────────────────────────────────────

    async def type_list(self) -> list[TypeRef]:
        return await self._call_list(TypeTools.LIST, {}, TypeRef)

    async def type_create(self, name: str) -> TypeRef:
        return await self._call(TypeTools.CREATE, {"name": name}, TypeRef)

    async def type_delete(self, type_id: str) -> bool:
        return await self._call_scalar(TypeTools.DELETE, {"type_id": type_id})

    # ──────────────────────────────────────────────────────────────────
    # issue CRUD + transition + close (7 op)
    # ──────────────────────────────────────────────────────────────────

    async def issue_create(self, doc: IssueCreate) -> IssueRead:
        return await self._call(
            IssueTools.CREATE, {"doc": doc.model_dump(mode="json")}, IssueRead,
        )

    async def issue_update(
        self, ref: str, patch: IssueUpdate,
    ) -> IssueRead | None:
        return await self._call_optional(
            IssueTools.UPDATE,
            {
                "ref": ref,
                "patch": patch.model_dump(mode="json", exclude_unset=True),
            },
            IssueRead,
        )

    async def issue_get(self, ref: str) -> IssueRead | None:
        return await self._call_optional(
            IssueTools.GET, {"ref": ref}, IssueRead,
        )

    async def issue_list(
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
        return await self._call_list(IssueTools.LIST, args, IssueRead)

    async def issue_close(self, ref: str) -> bool:
        return await self._call_scalar(IssueTools.CLOSE, {"ref": ref})

    async def issue_delete(self, ref: str) -> bool:
        return await self._call_scalar(IssueTools.DELETE, {"ref": ref})

    async def issue_count(self, *, where: dict[str, Any] | None = None) -> int:
        args: dict[str, Any] = {} if where is None else {"where": where}
        return await self._call_scalar(IssueTools.COUNT, args)

    async def issue_transition(self, ref: str, status_id: str) -> None:
        await self._call_scalar(
            IssueTools.TRANSITION, {"ref": ref, "status_id": status_id},
        )

    # ──────────────────────────────────────────────────────────────────
    # 내부 헬퍼 — FastMCP structuredContent 규약 흡수
    # ──────────────────────────────────────────────────────────────────

    async def _call(
        self, name: str, args: dict[str, Any], return_type: type[T],
    ) -> T:
        """Pydantic 모델 단건 — FastMCP 가 모델 dict 그대로 반환 (unwrapped)."""
        sc = await self._invoke(name, args)
        return return_type.model_validate(sc)

    async def _call_optional(
        self, name: str, args: dict[str, Any], return_type: type[T],
    ) -> T | None:
        """Optional[Model] — `{"result": <model_dict_or_None>}` 로 wrap."""
        sc = await self._invoke(name, args)
        inner = sc.get("result")
        if inner is None:
            return None
        return return_type.model_validate(inner)

    async def _call_list(
        self, name: str, args: dict[str, Any], item_type: type[T],
    ) -> list[T]:
        """list[T] — `{"result": [...]}` 로 wrap."""
        sc = await self._invoke(name, args)
        items = sc.get("result") or []
        return [item_type.model_validate(it) for it in items]

    async def _call_scalar(self, name: str, args: dict[str, Any]) -> Any:
        """bool / int / None 등 — `{"result": <scalar>}` 로 wrap."""
        sc = await self._invoke(name, args)
        return sc.get("result")

    async def _invoke(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        result = await self._mcp.call_tool(name, args)
        return result.structuredContent or {}


__all__ = ["IssueTrackerClient"]
