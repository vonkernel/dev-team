"""Primary 에이전트 FastAPI HTTP 서버.

langgraph-api 의존을 버리고 자체 구현한 A2A JSON-RPC 2.0 + AgentCard 제공.
영속 체크포인팅은 OSS `AsyncPostgresSaver` 를 `build_graph` 에 직접 주입.

엔드포인트:
  GET  /healthz                            - liveness
  GET  /.well-known/agent-card.json        - A2A AgentCard (spec §4.4)
  POST /a2a/{assistant_id}                 - A2A JSON-RPC 2.0 (SendMessage 최소)

환경변수:
  DATABASE_URI  (선택) - Postgres DSN. 있으면 AsyncPostgresSaver 로 영속 체크포인팅.
                        미설정 시 in-memory (재기동 시 상태 소실).
"""

from __future__ import annotations

import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import Any

from dev_team_shared.a2a import Message, Part, build_agent_card
from dev_team_shared.a2a.types import Role
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from primary_agent.graph import build_graph, build_llm, load_runtime_config

logger = logging.getLogger(__name__)

# assistant_id 는 role 이름 고정 사용 (langgraph-api 의 UUID 변환 없음 — 자체 구현).
_ASSISTANT_ID = "primary"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """기동: config 로드 → LLM 초기화 → (선택) Postgres checkpointer → graph compile."""
    config = load_runtime_config()
    persona = config.get("persona")
    if not persona:
        raise RuntimeError("config.persona is required")
    llm_cfg = config.get("llm") or {}

    llm = build_llm(llm_cfg)

    database_uri = os.environ.get("DATABASE_URI")
    if database_uri:
        # AsyncPostgresSaver 는 async context manager. app 수명 동안 연결 유지.
        async with AsyncPostgresSaver.from_conn_string(database_uri) as checkpointer:
            await checkpointer.setup()  # idempotent schema/table 생성
            graph = build_graph(persona=persona, llm=llm, checkpointer=checkpointer)
            app.state.graph = graph
            app.state.agent_card = build_agent_card(config)
            logger.info(
                "primary agent ready (Postgres checkpointer at %s)",
                _mask_dsn(database_uri),
            )
            yield
    else:
        graph = build_graph(persona=persona, llm=llm, checkpointer=None)
        app.state.graph = graph
        app.state.agent_card = build_agent_card(config)
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


@app.get("/healthz")
async def healthz() -> dict[str, bool]:
    return {"ok": True}


@app.get("/.well-known/agent-card.json")
async def agent_card_endpoint(request: Request) -> dict:
    """A2A Protocol v1.0 §4.4.1 — 에이전트 자기소개서."""
    card = request.app.state.agent_card
    return card.model_dump(by_alias=True, exclude_none=True)


@app.post("/a2a/{assistant_id}")
async def a2a_rpc(assistant_id: str, request: Request) -> JSONResponse:
    """A2A JSON-RPC 2.0 엔드포인트. M2 지원 메서드: `SendMessage`."""
    try:
        body = await request.json()
    except Exception as exc:
        return _rpc_error(None, -32700, f"parse error: {exc}")

    rpc_id = body.get("id")
    method = body.get("method")
    params = body.get("params") or {}

    if assistant_id != _ASSISTANT_ID:
        return _rpc_error(rpc_id, -32602, f"unknown assistant_id: {assistant_id!r}")

    if method == "SendMessage":
        return await _handle_send_message(request, rpc_id, params)

    return _rpc_error(rpc_id, -32601, f"method not found: {method!r}")


async def _handle_send_message(
    request: Request,
    rpc_id: Any,
    params: dict[str, Any],
) -> JSONResponse:
    try:
        a2a_msg = Message.model_validate(params.get("message") or {})
    except Exception as exc:
        return _rpc_error(rpc_id, -32602, f"invalid message: {exc}")

    human_parts = [p.text for p in a2a_msg.parts if p.text is not None]
    if not human_parts:
        return _rpc_error(rpc_id, -32602, "no text parts in message")
    human = HumanMessage(content="\n".join(human_parts))

    context_id = a2a_msg.context_id or str(uuid.uuid4())
    task_id = f"{context_id}:{uuid.uuid4()}"

    graph = request.app.state.graph
    try:
        result = await graph.ainvoke(
            {"messages": [human]},
            config={"configurable": {"thread_id": context_id}},
        )
    except Exception as exc:
        logger.exception("graph.ainvoke failed")
        err_reply = Message(
            message_id=f"err-{uuid.uuid4()}",
            role=Role.AGENT,
            parts=[Part(text=f"{type(exc).__name__}: {exc}")],
            context_id=context_id,
            task_id=task_id,
        )
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {
                    "task": {
                        "id": task_id,
                        "contextId": context_id,
                        "status": {
                            "state": "TASK_STATE_FAILED",
                            "message": err_reply.model_dump(
                                by_alias=True, exclude_none=True
                            ),
                        },
                        "history": [
                            a2a_msg.model_dump(by_alias=True, exclude_none=True),
                        ],
                    }
                },
            },
        )

    ai = next(
        (m for m in reversed(result["messages"]) if isinstance(m, AIMessage)),
        None,
    )
    ai_text = _stringify_ai_content(ai.content) if ai is not None else ""

    agent_reply = Message(
        message_id=f"reply-{uuid.uuid4()}",
        role=Role.AGENT,
        parts=[Part(text=ai_text)],
        context_id=context_id,
        task_id=task_id,
    )

    return JSONResponse(
        {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "result": {
                "task": {
                    "id": task_id,
                    "contextId": context_id,
                    "status": {"state": "TASK_STATE_COMPLETED"},
                    "history": [
                        a2a_msg.model_dump(by_alias=True, exclude_none=True),
                        agent_reply.model_dump(by_alias=True, exclude_none=True),
                    ],
                }
            },
        },
    )


def _rpc_error(rpc_id: Any, code: int, message: str) -> JSONResponse:
    return JSONResponse(
        {"jsonrpc": "2.0", "id": rpc_id, "error": {"code": code, "message": message}},
    )


def _stringify_ai_content(content: Any) -> str:
    """AIMessage.content 는 str 또는 content block 리스트. text 부분만 결합."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text" and "text" in item:
                    parts.append(str(item["text"]))
            elif isinstance(item, str):
                parts.append(item)
        return "".join(parts)
    return str(content)


def _mask_dsn(dsn: str) -> str:
    """비밀번호를 마스킹한 DSN 을 반환 (로그 안전성)."""
    if "@" in dsn and "://" in dsn:
        scheme, rest = dsn.split("://", 1)
        creds, host = rest.split("@", 1)
        if ":" in creds:
            user = creds.split(":", 1)[0]
            return f"{scheme}://{user}:***@{host}"
    return dsn


__all__ = ["app"]
