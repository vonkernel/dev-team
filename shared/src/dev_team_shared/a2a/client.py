"""A2A 경량 JSON-RPC 2.0 클라이언트.

langgraph-api 가 서버를 내장 제공하므로 우리는 주로 **상대 에이전트를 호출**하는
클라이언트 측 헬퍼를 제공한다. 서버 엔드포인트: `/a2a/{assistant_id}`.

A2A v1.0 JSON 직렬화 규약(§5.5):
- 필드명: camelCase
- enum: SCREAMING_SNAKE_CASE 문자열
- RPC 메서드명: PascalCase — `SendMessage`, `SendStreamingMessage`, `GetTask`
  단, langgraph-api 초기 버전은 구(舊) 명세의 슬래시 표기(`message/send` 등)를
  노출. 본 클라이언트는 `method_style` 설정으로 양쪽을 지원한다.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

import httpx

from dev_team_shared.a2a.tracing import TRACE_ID_HEADER
from dev_team_shared.a2a.types import Message

MethodStyle = Literal["pascal", "slash"]

_METHOD_MAP: dict[str, dict[MethodStyle, str]] = {
    "send_message": {"pascal": "SendMessage", "slash": "message/send"},
    "send_streaming_message": {
        "pascal": "SendStreamingMessage",
        "slash": "message/stream",
    },
    "get_task": {"pascal": "GetTask", "slash": "tasks/get"},
}


class A2AClientError(RuntimeError):
    """JSON-RPC 응답에 error 가 포함되었거나 HTTP 전송이 실패한 경우."""

    def __init__(self, message: str, *, code: int | None = None, data: Any | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.data = data


class A2AClient:
    """HTTP+JSON-RPC 2.0 기반 A2A 클라이언트.

    Args:
        endpoint: 상대 에이전트의 A2A 엔드포인트 URL.
            예: `http://architect:9000/a2a/architect`
        method_style: 서버가 지원하는 메서드 명명 스타일. 기본은 A2A v1.0 의 `pascal`.
        timeout: HTTP 타임아웃 (초).
        trace_id: 본 클라이언트가 모든 호출에 default 로 붙일 trace ID.
            위임 흐름에서는 매 호출마다 메서드 인자로 override 하는 것이 일반적.
            None 이면 헤더 미송신 → 수신 서버가 새로 발급. 자세한 규약:
            `dev_team_shared.a2a.tracing`.
    """

    def __init__(
        self,
        endpoint: str,
        *,
        method_style: MethodStyle = "pascal",
        timeout: float = 30.0,
        http_client: httpx.Client | None = None,
        trace_id: str | None = None,
    ) -> None:
        self._endpoint = endpoint
        self._style: MethodStyle = method_style
        self._timeout = timeout
        self._owns_client = http_client is None
        self._http = http_client or httpx.Client(timeout=timeout)
        self._default_trace_id = trace_id

    # ------------------------------------------------------------------
    # 공개 API
    # ------------------------------------------------------------------
    def send_message(
        self,
        message: Message,
        *,
        trace_id: str | None = None,
        **extra_params: Any,
    ) -> dict[str, Any]:
        """동기 요청-응답. 결과는 `Task` 또는 `Message` (서버 재량).

        `trace_id` 가 주어지면 이 호출에 한해 그 값으로 헤더 송신. 위임자는
        받은 요청의 trace_id 를 이 인자로 forward 하여 트리 전체를 한 trace 로
        묶는다.
        """
        return self._call(
            "send_message",
            self._message_params(message, extra_params),
            trace_id=trace_id,
        )

    def get_task(
        self,
        task_id: str,
        *,
        history_length: int | None = None,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """이전에 시작된 Task 의 상태/결과 조회."""
        params: dict[str, Any] = {"taskId": task_id}
        if history_length is not None:
            params["historyLength"] = history_length
        return self._call("get_task", params, trace_id=trace_id)

    def close(self) -> None:
        if self._owns_client:
            self._http.close()

    def __enter__(self) -> A2AClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # 내부 구현
    # ------------------------------------------------------------------
    def _call(
        self,
        logical_method: str,
        params: dict[str, Any],
        *,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        wire_method = _METHOD_MAP[logical_method][self._style]
        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": wire_method,
            "params": params,
        }
        # 헤더 우선순위: 메서드 인자 > 생성자 default. 둘 다 없으면 미송신.
        effective_trace = trace_id or self._default_trace_id
        headers = {TRACE_ID_HEADER: effective_trace} if effective_trace else None
        try:
            resp = self._http.post(self._endpoint, json=payload, headers=headers)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise A2AClientError(f"HTTP error calling {wire_method}: {e}") from e

        body = resp.json()
        if "error" in body:
            err = body["error"]
            raise A2AClientError(
                err.get("message", "A2A error"),
                code=err.get("code"),
                data=err.get("data"),
            )
        result = body.get("result")
        if result is None:
            raise A2AClientError("JSON-RPC response missing 'result'")
        return result

    @staticmethod
    def _message_params(message: Message, extra: dict[str, Any]) -> dict[str, Any]:
        # by_alias=True 로 camelCase 직렬화 + enum 은 StrEnum 이 그대로 문자열 직렬화
        return {"message": message.model_dump(by_alias=True, exclude_none=True), **extra}


__all__ = ["A2AClient", "A2AClientError", "MethodStyle"]
