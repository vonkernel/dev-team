"""WikiClient 의 도메인별 sub-client (현재 PageClient 1개).

#36 의 IssueTracker SDK 와 동일 패턴 (Protocol + sub-client + 컴포지트).
"""

from __future__ import annotations

from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

from dev_team_shared.wiki.schemas import (
    PageCreate,
    PageRead,
    PageRef,
    PageUpdate,
)
from dev_team_shared.wiki.tool_names import PageTools

T = TypeVar("T", bound=BaseModel)


class _Invoker(Protocol):
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


class PageClient:
    """페이지 CRUD (6 op)."""

    def __init__(self, invoker: _Invoker) -> None:
        self._invoker = invoker

    async def create(self, doc: PageCreate) -> PageRead:
        return await self._invoker.call(
            PageTools.CREATE, {"doc": doc.model_dump(mode="json")}, PageRead,
        )

    async def update(self, slug: str, patch: PageUpdate) -> PageRead | None:
        return await self._invoker.call_optional(
            PageTools.UPDATE,
            {"slug": slug, "patch": patch.model_dump(mode="json", exclude_unset=True)},
            PageRead,
        )

    async def get(self, slug: str) -> PageRead | None:
        return await self._invoker.call_optional(
            PageTools.GET, {"slug": slug}, PageRead,
        )

    async def list(self) -> list[PageRef]:
        return await self._invoker.call_list(PageTools.LIST, {}, PageRef)

    async def delete(self, slug: str) -> bool:
        return await self._invoker.call_scalar(PageTools.DELETE, {"slug": slug})

    async def count(self) -> int:
        return await self._invoker.call_scalar(PageTools.COUNT, {})


__all__ = ["PageClient", "_Invoker"]
