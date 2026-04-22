"""JSON-RPC 2.0 envelope 헬퍼.

A2A transport 계층에서 쓰는 JSON-RPC 2.0 요청/응답/에러 구조와 표준 에러 코드를
제공. 서버는 `rpc_result_response`, `rpc_error_response` 로 응답 dict 를 조립한다.

spec: https://www.jsonrpc.org/specification
"""

from __future__ import annotations

from typing import Any, Final

# JSON-RPC 2.0 표준 에러 코드 (§5.1 Error object)
PARSE_ERROR: Final[int] = -32700
INVALID_REQUEST: Final[int] = -32600
METHOD_NOT_FOUND: Final[int] = -32601
INVALID_PARAMS: Final[int] = -32602
INTERNAL_ERROR: Final[int] = -32603


def rpc_result_response(rpc_id: Any, result: Any) -> dict[str, Any]:
    """JSON-RPC 2.0 성공 응답 dict."""
    return {"jsonrpc": "2.0", "id": rpc_id, "result": result}


def rpc_error_response(
    rpc_id: Any,
    code: int,
    message: str,
    data: Any | None = None,
) -> dict[str, Any]:
    """JSON-RPC 2.0 에러 응답 dict."""
    err: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": rpc_id, "error": err}


__all__ = [
    "INTERNAL_ERROR",
    "INVALID_PARAMS",
    "INVALID_REQUEST",
    "METHOD_NOT_FOUND",
    "PARSE_ERROR",
    "rpc_error_response",
    "rpc_result_response",
]
