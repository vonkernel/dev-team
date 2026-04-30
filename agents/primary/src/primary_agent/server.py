"""Primary 에이전트 FastAPI HTTP 서버.

공용 A2A 라우터 팩토리(`shared.a2a.server.make_a2a_router`)와 공용 LangGraph
핸들러(`shared.a2a.server.graph_handlers`) 위에 얇은 조립 레이어.
이 모듈의 책임은 다음 세 가지로 국한된다:

  1) Role Config 로드 → persona / LLM / AsyncPostgresSaver 준비 (lifespan)
  2) 그래프 compile → `app.state.graph` 세팅
  3) AgentCard 빌드 → `app.state.agent_card` 세팅
  4) A2A 라우터 `include_router` (method handler 등록)

A2A 프로토콜 레이어(Task / Event 직렬화, SSE, JSON-RPC envelope) 는 전부
shared 에 있으며, 본 파일에서 **프로토콜 로직을 다시 작성하지 않는다**.

환경변수:
  ANTHROPIC_API_KEY  (필수, overrides/primary.yaml 통해 config 에 치환)
  DATABASE_URI       (선택) - Postgres DSN. 있으면 AsyncPostgresSaver 로 영속 체크포인팅.
                             미설정 시 in-memory (재기동 시 상태 소실).
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
from fastapi import FastAPI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from primary_agent.graph import build_graph, build_llm, load_runtime_config

# uvicorn 은 자체 logger 만 INFO 로 올려두므로 app · shared logger 도 명시적 INFO.
# shared/a2a/server/graph_handlers 의 sse_session.start/end 같은 lifecycle 로그가
# stdout 에 흐르려면 root logger level 이 INFO 여야 함.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

_ASSISTANT_ID = "primary"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """기동: config → LLM → (선택) Postgres checkpointer → graph compile → state 세팅."""
    config = load_runtime_config()
    persona = config.get("persona")
    if not persona:
        raise RuntimeError("config.persona is required")
    llm = build_llm(config.get("llm") or {})

    database_uri = os.environ.get("DATABASE_URI")
    agent_card = build_agent_card(config)

    if database_uri:
        async with AsyncPostgresSaver.from_conn_string(database_uri) as checkpointer:
            await checkpointer.setup()  # idempotent schema/table 생성
            app.state.graph = build_graph(
                persona=persona, llm=llm, checkpointer=checkpointer,
            )
            app.state.agent_card = agent_card
            logger.info(
                "primary agent ready (Postgres checkpointer at %s)",
                _mask_dsn(database_uri),
            )
            yield
    else:
        app.state.graph = build_graph(persona=persona, llm=llm, checkpointer=None)
        app.state.agent_card = agent_card
        logger.warning(
            "DATABASE_URI not set — running with in-memory state "
            "(non-durable across restarts)",
        )
        yield


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
