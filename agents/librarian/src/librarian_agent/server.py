"""Librarian (L) 에이전트 FastAPI HTTP 서버.

Primary 의 server.py 미러 + DocStoreClient (MCP) wiring.

lifespan 책임:
  1) Role Config 로드 → persona / LLM 준비
  2) DocStoreClient (Streamable HTTP MCP) 연결 → tools build → graph compile
  3) (선택) AsyncPostgresSaver wiring
  4) AgentCard build → app.state 세팅
  5) 공용 A2A 라우터 include

환경변수:
  ANTHROPIC_API_KEY       (필수, overrides/librarian.yaml 통해 주입)
  DOC_STORE_MCP_URL       (필수, 예: http://doc-store-mcp:8000/mcp)
  DATABASE_URI            (선택, 미설정 시 in-memory checkpointer)
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from dev_team_shared.a2a import build_agent_card
from dev_team_shared.a2a.server import make_a2a_router
from dev_team_shared.a2a.server.graph_handlers import (
    GraphSendMessageHandler,
    GraphSendStreamingMessageHandler,
)
from dev_team_shared.doc_store import DocStoreClient
from dev_team_shared.mcp_client import StreamableMCPClient
from fastapi import FastAPI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from librarian_agent.graph import build_graph, build_llm, load_runtime_config
from librarian_agent.tools import build_tools

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

_ASSISTANT_ID = "librarian"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """기동: config → LLM → MCP client → tools → graph compile → state 세팅."""
    config = load_runtime_config()
    persona = config.get("persona")
    if not persona:
        raise RuntimeError("config.persona is required")
    llm = build_llm(config.get("llm") or {})

    doc_store_url = os.environ.get("DOC_STORE_MCP_URL")
    if not doc_store_url:
        raise RuntimeError("DOC_STORE_MCP_URL env required")
    database_uri = os.environ.get("DATABASE_URI")
    agent_card = build_agent_card(config)

    # Doc Store MCP 연결 — lifespan 동안 유지. shutdown 에서 aclose.
    mcp = await StreamableMCPClient.connect(doc_store_url)
    try:
        client = DocStoreClient(mcp)
        tools = build_tools(client)
        logger.info(
            "librarian agent ready (doc_store=%s, tools=%d)",
            doc_store_url,
            len(tools),
        )

        if database_uri:
            async with AsyncPostgresSaver.from_conn_string(database_uri) as checkpointer:
                await checkpointer.setup()
                app.state.graph = build_graph(
                    persona=persona, llm=llm, tools=tools, checkpointer=checkpointer,
                )
                app.state.agent_card = agent_card
                logger.info(
                    "librarian agent ready (Postgres checkpointer at %s)",
                    _mask_dsn(database_uri),
                )
                yield
        else:
            app.state.graph = build_graph(
                persona=persona, llm=llm, tools=tools, checkpointer=None,
            )
            app.state.agent_card = agent_card
            logger.warning(
                "DATABASE_URI not set — running with in-memory state "
                "(non-durable across restarts)",
            )
            yield
    finally:
        await mcp.aclose()


app = FastAPI(
    lifespan=lifespan,
    title="Librarian Agent (dev-team)",
    description=(
        "A2A-compatible LangGraph agent — Doc Store 단일 창구. "
        "자연어 → tool 매핑 (LLM ReAct)."
    ),
)

app.include_router(
    make_a2a_router(
        assistant_id=_ASSISTANT_ID,
        handlers=[
            GraphSendMessageHandler(),
            GraphSendStreamingMessageHandler(),
        ],
    ),
)


def _mask_dsn(dsn: str) -> str:
    if "@" in dsn and "://" in dsn:
        scheme, rest = dsn.split("://", 1)
        creds, host = rest.split("@", 1)
        if ":" in creds:
            user = creds.split(":", 1)[0]
            return f"{scheme}://{user}:***@{host}"
    return dsn


__all__ = ["app"]
