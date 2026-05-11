"""StreamableMCPClient — streamable HTTP MCP 클라이언트 wrapper.

`mcp` SDK 의 streamablehttp_client + ClientSession 을 lifespan-friendly 컨텍스트
매니저로 래핑. 호출자는 `connect()` 후 `call_tool()` / `aclose()` 만 알면 됨.

#75 PR 4: MCP 서버 (예: doc-store-mcp) 재시작 시 우리 측 long-lived session 이
`McpError("Session terminated")` 로 끊김. `call_tool` 이 자동 재연결 + 1회
retry — caller 측 흐름 차단 없이 복구.
"""

from __future__ import annotations

import logging
from contextlib import AsyncExitStack
from datetime import timedelta
from typing import Any

import anyio
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.shared.exceptions import McpError

logger = logging.getLogger(__name__)


class StreamableMCPClient:
    """단일 MCP 서버에 대한 long-lived 클라이언트.

    `connect(url)` 으로 생성 → `call_tool(...)` 호출 → `aclose()` 로 정리.
    또는 `async with StreamableMCPClient.connect(url) as client:` 패턴.

    `call_tool` 은 자동 reconnect — server restart 등으로 session terminated
    감지 시 1회 재연결 + retry. 재연결도 실패하면 예외 그대로 propagate.
    """

    def __init__(
        self,
        session: ClientSession,
        stack: AsyncExitStack,
        *,
        url: str,
        read_timeout_seconds: float,
    ) -> None:
        self._session = session
        self._stack = stack
        self._url = url
        self._read_timeout_seconds = read_timeout_seconds
        self._reconnect_lock = anyio.Lock()

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
            session = await cls._build_session(url, stack, read_timeout_seconds)
            return cls(
                session, stack,
                url=url, read_timeout_seconds=read_timeout_seconds,
            )
        except Exception:
            await stack.aclose()
            raise

    @staticmethod
    async def _build_session(
        url: str, stack: AsyncExitStack, read_timeout_seconds: float,
    ) -> ClientSession:
        transport = await stack.enter_async_context(streamablehttp_client(url))
        read, write, _ = transport
        session = await stack.enter_async_context(
            ClientSession(
                read, write,
                read_timeout_seconds=timedelta(seconds=read_timeout_seconds),
            ),
        )
        await session.initialize()
        return session

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """도구 호출. session terminated 시 1회 재연결 + retry.

        `isError=True` 면 RuntimeError 로 변환 (caller 가 처리).
        """
        try:
            return await self._invoke(name, arguments)
        except McpError as exc:
            if not _is_session_terminated(exc):
                raise
            logger.warning(
                "MCP session terminated for %s — reconnecting + retry",
                self._url,
            )
            await self._reconnect()
            return await self._invoke(name, arguments)

    async def _invoke(self, name: str, arguments: dict[str, Any]) -> Any:
        result = await self._session.call_tool(name, arguments)
        if result.isError:
            text = result.content[0].text if result.content else "tool error (no content)"
            raise RuntimeError(f"MCP tool {name!r} returned error: {text}")
        return result

    async def _reconnect(self) -> None:
        """기존 session aclose 후 새로 연결. lock 으로 동시 reconnect 직렬화."""
        async with self._reconnect_lock:
            old_stack = self._stack
            new_stack = AsyncExitStack()
            try:
                self._session = await self._build_session(
                    self._url, new_stack, self._read_timeout_seconds,
                )
                self._stack = new_stack
                logger.info("MCP session reconnected to %s", self._url)
            except Exception:
                await new_stack.aclose()
                raise
            finally:
                try:
                    await old_stack.aclose()
                except Exception:
                    logger.exception(
                        "old MCP stack close failed during reconnect (url=%s)",
                        self._url,
                    )

    async def aclose(self) -> None:
        await self._stack.aclose()

    async def __aenter__(self) -> StreamableMCPClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()


def _is_session_terminated(exc: McpError) -> bool:
    """McpError 가 'Session terminated' (server restart 등) 인지 판정.

    SDK 가 별 클래스로 구분 안 하니 메시지 substring 으로 (best-effort).
    """
    msg = str(exc).lower()
    return "session terminated" in msg or "session not found" in msg


__all__ = ["StreamableMCPClient"]
