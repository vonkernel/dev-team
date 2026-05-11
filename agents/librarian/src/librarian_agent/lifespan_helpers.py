"""Librarian lifespan 의 agent-specific helper.

shared 인 부분 (`build_event_bus`, `build_checkpointer`, `mask_dsn`) 은
`dev_team_shared.lifespan` 으로 추출됨. 본 모듈은 Librarian 특수 helper 만:

- `build_doc_store_client` — Doc Store MCP streamable HTTP 연결 + cleanup
- `log_runtime_ready` — Librarian tools 카탈로그 한 줄

shared helper 는 본 모듈에서 re-export — server.py 등의 import 경로 호환.
"""

from __future__ import annotations

import logging
from contextlib import AsyncExitStack

from dev_team_shared.doc_store import DocStoreClient
# shared helpers — server.py 가 본 모듈에서 import 하는 호환성 위해 re-export.
from dev_team_shared.lifespan import (  # noqa: F401  re-export
    build_checkpointer,
    build_event_bus,
    mask_dsn,
)
from dev_team_shared.mcp_client import StreamableMCPClient
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)


async def build_doc_store_client(
    doc_store_url: str, stack: AsyncExitStack,
) -> DocStoreClient:
    """Doc Store MCP 연결 + cleanup 을 stack 에 등록 → DocStoreClient 반환."""
    mcp = await StreamableMCPClient.connect(doc_store_url)
    stack.push_async_callback(mcp.aclose)
    logger.info("doc_store MCP ready (%s)", doc_store_url)
    return DocStoreClient(mcp)


def log_runtime_ready(tools: list[BaseTool]) -> None:
    """기동 완료 시점의 tool 카탈로그 한 줄 요약."""
    logger.info("librarian tools wired: doc_store=on, total=%d", len(tools))


__all__ = [
    "build_checkpointer",
    "build_doc_store_client",
    "build_event_bus",
    "log_runtime_ready",
    "mask_dsn",
]
