"""WikiClient — Wiki MCP 의 typed 클라이언트.

ISP / composition: 도메인별 sub-client (현재 `pages` 만, 향후 확장).

사용:

    async with await StreamableMCPClient.connect(url) as mcp:
        client = WikiClient(mcp)
        page = await client.pages.create(PageCreate(slug="prd-x", title="...", content_md="..."))
        await client.pages.update("prd-x", PageUpdate(content_md="..."))
        await client.pages.delete("prd-x")
"""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

from dev_team_shared.mcp_client import StreamableMCPClient
from dev_team_shared.wiki._ops_client import PageClient

T = TypeVar("T", bound=BaseModel)


class WikiClient:
    """sub-client 의 컴포지트 — 외부 진입점."""

    def __init__(self, mcp: StreamableMCPClient) -> None:
        self._mcp = mcp
        invoker = _MCPInvoker(mcp)
        self._pages = PageClient(invoker)

    @property
    def pages(self) -> PageClient:
        return self._pages


class _MCPInvoker:
    """FastMCP structuredContent 규약 흡수.

    - Pydantic 모델 단건 → 모델 dict 그대로 (unwrapped)
    - Optional / list / scalar → `{"result": <value>}` 로 wrap
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


__all__ = ["WikiClient"]
