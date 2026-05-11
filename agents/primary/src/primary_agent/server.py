"""Primary 에이전트 FastAPI HTTP 서버.

lifespan = 비즈니스 흐름 조립만:

  1) `Settings.from_env()` — env 변수 → frozen settings
  2) `_build_runtime_inputs()` — config → persona / LLM / agent_card
  3) `build_event_bus` — Valkey 활성 시 publish 활성화
  4) `build_channels` — 4 채널 client 인스턴스화 (lifecycle 은 stack 등록)
  5) `build_tools` — 4 채널 → LangChain tool 묶음
  6) `build_checkpointer` — DSN 활성 시 Postgres 영속, 미활성 시 in-memory
  7) `build_graph` → `app.state` 세팅

각 단계의 디테일 (env read / try-except / cleanup 등록 / DSN 마스킹) 은
모듈별 helper 가 담당 (SRP). 본 파일은 호출 순서만.

A2A 프로토콜 레이어 (Task / Event / SSE / JSON-RPC) 는 shared 에 있고 본
파일에서 다시 작성하지 않는다.

환경변수: 자세한 설명은 `Settings.from_env()` + 각 helper docstring.
"""

from __future__ import annotations

import logging
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any

from dev_team_shared.a2a import build_agent_card
from dev_team_shared.a2a.server import make_a2a_router
from dev_team_shared.a2a.server.graph_handlers import (
    GraphSendMessageHandler,
    GraphSendStreamingMessageHandler,
)
from fastapi import FastAPI
from langchain_core.language_models import BaseChatModel

from primary_agent.channels import build_channels
from primary_agent.chat_handler import SessionRegistry, make_chat_router
from primary_agent.graph import build_graph, build_llm, load_runtime_config
from primary_agent.lifespan_helpers import (
    build_checkpointer,
    build_event_bus,
    log_runtime_ready,
)
from primary_agent.settings import Settings
from primary_agent.tools import build_tools

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

_ASSISTANT_ID = "primary"


def _build_runtime_inputs() -> tuple[str, BaseChatModel, dict[str, Any]]:
    """config 로드 → (persona, LLM, raw_config) 추출. agent_card 빌드는 호출자 책임."""
    config = load_runtime_config()
    persona = config.get("persona")
    if not persona:
        raise RuntimeError("config.persona is required")
    llm = build_llm(config.get("llm") or {})
    return persona, llm, config


@asynccontextmanager
async def lifespan(app: FastAPI):
    """기동: settings → runtime inputs → infra (event_bus / channels / checkpointer) → tools → graph."""
    settings = Settings.from_env()
    persona, llm, config = _build_runtime_inputs()
    agent_card = build_agent_card(config)

    async with AsyncExitStack() as stack:
        event_bus = await build_event_bus(settings.valkey_url, stack)
        channels = await build_channels(settings, stack)
        tools = build_tools(
            doc_store=channels.doc_store,
            issue_tracker=channels.issue_tracker,
            wiki=channels.wiki,
            librarian=channels.librarian,
            event_bus=event_bus,
        )
        checkpointer = await build_checkpointer(settings.database_uri, stack)

        app.state.graph = build_graph(
            persona=persona, llm=llm, tools=tools, checkpointer=checkpointer,
        )
        app.state.agent_card = agent_card
        app.state.event_bus = event_bus
        # #75 PR 4: chat protocol session registry (in-memory)
        app.state.chat_session_registry = SessionRegistry()
        stack.push_async_callback(app.state.chat_session_registry.aclose)
        log_runtime_ready(channels, tools)
        yield


app = FastAPI(
    lifespan=lifespan,
    title="Primary Agent (dev-team)",
    description="A2A-compatible LangGraph agent — self-hosted OSS path.",
)

# 공용 A2A 라우터 — 메서드 추가는 shared 의 MethodHandler 구현체 등록으로 (OCP).
app.include_router(
    make_a2a_router(
        assistant_id=_ASSISTANT_ID,
        handlers=[
            GraphSendMessageHandler(),
            GraphSendStreamingMessageHandler(),
        ],
    ),
)

# #75 PR 4: chat protocol — UG↔P chat tier server-side.
# POST /chat/send + GET /chat/stream
app.include_router(make_chat_router())


__all__ = ["app"]
