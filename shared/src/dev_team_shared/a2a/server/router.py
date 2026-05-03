"""A2A FastAPI 라우터 팩토리.

`make_a2a_router` 는 임의의 에이전트에 재사용 가능한 공용 구성을 반환:

    GET  /healthz                         — liveness
    GET  /.well-known/agent-card.json     — AgentCard (app.state.agent_card 사용)
    POST /a2a/{assistant_id}              — JSON-RPC 2.0 dispatch

각 에이전트의 `server.py` 는 lifespan 에서 `app.state.graph` / `app.state.agent_card`
를 세팅하고, 원하는 `MethodHandler` 목록과 함께 본 팩토리를 호출해 include_router 한다.

규약:
- app.state.agent_card: AgentCard 인스턴스 (FastAPI `request.app.state` 를 통해 접근).
- 각 MethodHandler 는 자신의 자원(예: graph) 을 동일하게 app.state 에서 lookup.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from dev_team_shared.a2a.jsonrpc import (
    INVALID_PARAMS,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    rpc_error_response,
)
from dev_team_shared.a2a.server.handler import MethodHandler
from dev_team_shared.a2a.tracing import TRACE_ID_HEADER


def make_a2a_router(
    *,
    assistant_id: str,
    handlers: Sequence[MethodHandler],
) -> APIRouter:
    """A2A 엔드포인트를 마운트한 APIRouter 반환.

    Args:
        assistant_id: 이 서버가 응답하는 assistant 이름 (URL path segment).
            `POST /a2a/{aid}` 의 `aid` 가 이 값과 다르면 INVALID_PARAMS 에러.
        handlers: 등록할 MethodHandler 구현체 목록. 각자의 `method_name` 이
            key 가 된다.

    Raises:
        ValueError: handlers 중 중복된 method_name 이 있을 때.
    """
    registry: dict[str, MethodHandler] = {}
    for h in handlers:
        if h.method_name in registry:
            raise ValueError(
                f"duplicate A2A method handler: {h.method_name!r} "
                f"({type(registry[h.method_name]).__name__} vs {type(h).__name__})",
            )
        registry[h.method_name] = h

    router = APIRouter()

    @router.get("/healthz")
    async def healthz() -> dict[str, bool]:
        return {"ok": True}

    @router.get("/.well-known/agent-card.json")
    async def agent_card_endpoint(request: Request) -> dict:
        card = request.app.state.agent_card
        return card.model_dump(by_alias=True, exclude_none=True)

    @router.post("/a2a/{aid}")
    async def a2a_rpc(aid: str, request: Request):
        # trace_id: 클라이언트가 보낸 헤더가 우선, 없으면 서버가 발급.
        # 핸들러는 request.state.trace_id 로 lookup (per-request 데이터).
        request.state.trace_id = (
            request.headers.get(TRACE_ID_HEADER) or str(uuid.uuid4())
        )

        try:
            body = await request.json()
        except Exception as exc:
            return JSONResponse(
                rpc_error_response(None, PARSE_ERROR, f"parse error: {exc}"),
            )

        rpc_id = body.get("id")
        method = body.get("method")
        params = body.get("params") or {}

        if aid != assistant_id:
            return JSONResponse(
                rpc_error_response(
                    rpc_id, INVALID_PARAMS, f"unknown assistant_id: {aid!r}",
                ),
            )

        handler = registry.get(method)
        if handler is None:
            return JSONResponse(
                rpc_error_response(
                    rpc_id, METHOD_NOT_FOUND, f"method not found: {method!r}",
                ),
            )

        return await handler.handle(request, rpc_id, params)

    return router


__all__ = ["make_a2a_router"]
