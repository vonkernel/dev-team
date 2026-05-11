"""JSON-RPC 2.0 / SSE envelope 직렬화.

Pydantic 모델 → wire 표현으로 한 단계 변환. 단방향 응답은 `JSONResponse`,
스트리밍 라인은 SSE `data: ...` 문자열.
"""

from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse

from dev_team_shared.a2a.jsonrpc import rpc_result_response
from dev_team_shared.a2a.server.graph_handlers.rpc import RPCContext
from dev_team_shared.a2a.server.sse import sse_pack


def rpc_result(ctx: RPCContext, model: Any) -> dict[str, Any]:
    """Pydantic 모델을 JSON-RPC 2.0 result 응답 dict 로."""
    return rpc_result_response(
        ctx.rpc_id, model.model_dump(by_alias=True, exclude_none=True),
    )


def sse(ctx: RPCContext, model: Any) -> str:
    """Pydantic 모델을 SSE `data:` 라인 문자열로."""
    return sse_pack(rpc_result(ctx, model))


def json_response(ctx: RPCContext, model: Any) -> JSONResponse:
    """Pydantic 모델을 단방향 JSON-RPC 응답으로."""
    return JSONResponse(rpc_result(ctx, model))


__all__ = ["json_response", "rpc_result", "sse"]
