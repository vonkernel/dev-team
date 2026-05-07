"""Primary 에이전트 FastAPI HTTP 서버.

공용 A2A 라우터 팩토리(`shared.a2a.server.make_a2a_router`)와 공용 LangGraph
핸들러(`shared.a2a.server.graph_handlers`) 위에 얇은 조립 레이어.
이 모듈의 책임은 다음으로 국한된다:

  1) Role Config 로드 → persona / LLM / AsyncPostgresSaver 준비 (lifespan)
  2) 4 채널 클라이언트 wiring (Doc Store / IssueTracker / Wiki / Librarian
     A2A) — env 로 제공된 URL 만 활성. 미제공 시 해당 도구 미노출.
  3) 그래프 compile (도구 통합) → `app.state.graph` 세팅
  4) AgentCard 빌드 → `app.state.agent_card` 세팅
  5) A2A 라우터 `include_router` (method handler 등록)

A2A 프로토콜 레이어(Task / Event 직렬화, SSE, JSON-RPC envelope) 는 전부
shared 에 있으며, 본 파일에서 **프로토콜 로직을 다시 작성하지 않는다**.

환경변수:
  ANTHROPIC_API_KEY        (필수, overrides/primary.yaml 통해 config 에 치환)
  DATABASE_URI             (선택) - Postgres DSN. 있으면 AsyncPostgresSaver 로 영속 체크포인팅.
                                    미설정 시 in-memory (재기동 시 상태 소실).
  VALKEY_URL               (선택) - 있으면 ValkeyEventBus 로 A2A 대화 이벤트 publish (#34).
  DOC_STORE_MCP_URL        (필수, 예: http://doc-store-mcp:8000/mcp) - PM 자기 도메인 영속.
  ISSUE_TRACKER_MCP_URL    (선택) - 외부 GitHub Issue sync. 미설정 시 외부 이슈 도구 미노출.
  WIKI_MCP_URL             (선택) - 외부 GitHub Wiki sync. 미설정 시 외부 wiki 도구 미노출.
  LIBRARIAN_A2A_URL        (선택) - Librarian A2A 엔드포인트. 미설정 시 librarian_query 도구 미노출.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from dev_team_shared.a2a import build_agent_card
from dev_team_shared.a2a.client import A2AClient
from dev_team_shared.a2a.server import make_a2a_router
from dev_team_shared.a2a.server.graph_handlers import (
    GraphSendMessageHandler,
    GraphSendStreamingMessageHandler,
)
from dev_team_shared.doc_store import DocStoreClient
from dev_team_shared.event_bus import ValkeyEventBus
from dev_team_shared.issue_tracker import IssueTrackerClient
from dev_team_shared.mcp_client import StreamableMCPClient
from dev_team_shared.wiki import WikiClient
from fastapi import FastAPI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from primary_agent.graph import build_graph, build_llm, load_runtime_config
from primary_agent.tools import build_tools

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

_ASSISTANT_ID = "primary"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """기동: config → LLM → 4 채널 클라이언트 → tools → graph compile → state 세팅."""
    config = load_runtime_config()
    persona = config.get("persona")
    if not persona:
        raise RuntimeError("config.persona is required")
    llm = build_llm(config.get("llm") or {})

    doc_store_url = os.environ.get("DOC_STORE_MCP_URL")
    if not doc_store_url:
        raise RuntimeError("DOC_STORE_MCP_URL env required (#39)")
    issue_tracker_url = os.environ.get("ISSUE_TRACKER_MCP_URL")
    wiki_url = os.environ.get("WIKI_MCP_URL")
    librarian_url = os.environ.get("LIBRARIAN_A2A_URL")
    database_uri = os.environ.get("DATABASE_URI")
    valkey_url = os.environ.get("VALKEY_URL")
    agent_card = build_agent_card(config)

    # 이벤트 브로커 (선택)
    event_bus: ValkeyEventBus | None = None
    if valkey_url:
        try:
            event_bus = await ValkeyEventBus.create(valkey_url)
            logger.info("event_bus ready (Valkey at %s)", valkey_url)
        except Exception:
            logger.exception(
                "ValkeyEventBus 초기화 실패 (url=%s) — publish 비활성화로 진행",
                valkey_url,
            )
            event_bus = None
    else:
        logger.info("VALKEY_URL not set — A2A 이벤트 publish 비활성화")

    # 4 채널 클라이언트 — env 활성된 것만 wiring.
    doc_store_mcp = await StreamableMCPClient.connect(doc_store_url)
    issue_tracker_mcp: StreamableMCPClient | None = None
    wiki_mcp: StreamableMCPClient | None = None
    librarian_a2a: A2AClient | None = None

    try:
        doc_store = DocStoreClient(doc_store_mcp)

        issue_tracker: IssueTrackerClient | None = None
        if issue_tracker_url:
            issue_tracker_mcp = await StreamableMCPClient.connect(issue_tracker_url)
            issue_tracker = IssueTrackerClient(issue_tracker_mcp)
            logger.info("issue_tracker ready (%s)", issue_tracker_url)

        wiki: WikiClient | None = None
        if wiki_url:
            wiki_mcp = await StreamableMCPClient.connect(wiki_url)
            wiki = WikiClient(wiki_mcp)
            logger.info("wiki ready (%s)", wiki_url)

        if librarian_url:
            librarian_a2a = A2AClient(librarian_url)
            logger.info("librarian A2A ready (%s)", librarian_url)

        tools = build_tools(
            doc_store=doc_store,
            issue_tracker=issue_tracker,
            wiki=wiki,
            librarian=librarian_a2a,
        )
        logger.info(
            "primary tools wired: doc_store=on, issue_tracker=%s, wiki=%s, librarian=%s, total=%d",
            "on" if issue_tracker else "off",
            "on" if wiki else "off",
            "on" if librarian_a2a else "off",
            len(tools),
        )

        if database_uri:
            async with AsyncPostgresSaver.from_conn_string(database_uri) as checkpointer:
                await checkpointer.setup()  # idempotent schema/table 생성
                app.state.graph = build_graph(
                    persona=persona, llm=llm, tools=tools, checkpointer=checkpointer,
                )
                app.state.agent_card = agent_card
                app.state.event_bus = event_bus
                logger.info(
                    "primary agent ready (Postgres checkpointer at %s)",
                    _mask_dsn(database_uri),
                )
                yield
        else:
            app.state.graph = build_graph(
                persona=persona, llm=llm, tools=tools, checkpointer=None,
            )
            app.state.agent_card = agent_card
            app.state.event_bus = event_bus
            logger.warning(
                "DATABASE_URI not set — running with in-memory state "
                "(non-durable across restarts)",
            )
            yield
    finally:
        if librarian_a2a is not None:
            librarian_a2a.close()
        if wiki_mcp is not None:
            await wiki_mcp.aclose()
        if issue_tracker_mcp is not None:
            await issue_tracker_mcp.aclose()
        await doc_store_mcp.aclose()
        if event_bus is not None:
            await event_bus.aclose()


app = FastAPI(
    lifespan=lifespan,
    title="Primary Agent (dev-team)",
    description="A2A-compatible LangGraph agent — self-hosted OSS path.",
)

# 공용 A2A 라우터 — 이 에이전트가 지원하는 메서드만 핸들러로 등록.
# 메서드 추가 시 shared 의 MethodHandler 구현체 하나 더 등록하면 된다 (OCP).
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
    """비밀번호를 마스킹한 DSN (로그 안전성)."""
    if "@" in dsn and "://" in dsn:
        scheme, rest = dsn.split("://", 1)
        creds, host = rest.split("@", 1)
        if ":" in creds:
            user = creds.split(":", 1)[0]
            return f"{scheme}://{user}:***@{host}"
    return dsn


__all__ = ["app"]
