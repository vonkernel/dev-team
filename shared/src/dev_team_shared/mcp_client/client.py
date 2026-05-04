"""StreamableMCPClient — streamable HTTP MCP 클라이언트 wrapper.

`mcp` SDK 의 streamablehttp_client + ClientSession 을 lifespan-friendly 컨텍스트
매니저로 래핑. 호출자는 `connect()` 후 `call_tool()` / `aclose()` 만 알면 됨.
"""

from __future__ import annotations

from contextlib import AsyncExitStack
from datetime import timedelta
from typing import Any

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client


class StreamableMCPClient:
    """단일 MCP 서버에 대한 long-lived 클라이언트.

    `connect(url)` 으로 생성 → `call_tool(...)` 호출 → `aclose()` 로 정리.
    또는 `async with StreamableMCPClient.connect(url) as client:` 패턴.
    """

    def __init__(self, session: ClientSession, stack: AsyncExitStack) -> None:
        self._session = session
        self._stack = stack

    @classmethod
    async def connect(
        cls,
        url: str,
        *,
        read_timeout_seconds: float = 30.0,
    ) -> StreamableMCPClient:
        """MCP 서버에 연결 + initialize. 실패 시 자원 정리 후 raise."""
        stack = AsyncExitStack()
        try:
            transport = await stack.enter_async_context(streamablehttp_client(url))
            read, write, _ = transport
            session = await stack.enter_async_context(
                ClientSession(
                    read,
                    write,
                    read_timeout_seconds=timedelta(seconds=read_timeout_seconds),
                ),
            )
            await session.initialize()
            return cls(session, stack)
        except Exception:
            await stack.aclose()
            raise

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """도구 호출. `isError=True` 면 RuntimeError 로 변환 (caller 가 처리)."""
        result = await self._session.call_tool(name, arguments)
        if result.isError:
            # 첫 content 의 text 를 에러 메시지로
            text = result.content[0].text if result.content else "tool error (no content)"
            raise RuntimeError(f"MCP tool {name!r} returned error: {text}")
        return result

    async def aclose(self) -> None:
        await self._stack.aclose()

    async def __aenter__(self) -> StreamableMCPClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()


__all__ = ["StreamableMCPClient"]
