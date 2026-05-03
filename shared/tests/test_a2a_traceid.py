"""traceId 운반 규약 테스트.

대상:
- `A2AClient` 가 `X-A2A-Trace-Id` 헤더 송신 (생성자 default / 메서드 override).
- `make_a2a_router` 가 헤더 읽어 `request.state.trace_id` 에 보관.
  - 헤더 부재 시 새 UUID 발급.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from dev_team_shared.a2a import A2AClient, TRACE_ID_HEADER
from dev_team_shared.a2a.types import Message, Part, Role
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from dev_team_shared.a2a.server import make_a2a_router
from dev_team_shared.a2a.server.handler import MethodHandler


def _client(responder, *, trace_id: str | None = None):  # type: ignore[no-untyped-def]
    transport = httpx.MockTransport(responder)
    http = httpx.Client(transport=transport)
    return A2AClient(
        "http://peer:9000/a2a/peer",
        http_client=http,
        trace_id=trace_id,
    )


class TestClientSendsTraceHeader:
    def test_no_trace_id_means_no_header(self) -> None:
        seen: dict[str, Any] = {}

        def responder(request: httpx.Request) -> httpx.Response:
            seen["headers"] = dict(request.headers)
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": "x", "result": {}})

        with _client(responder) as c:
            c.send_message(Message(message_id="m", role=Role.USER, parts=[Part(text="hi")]))

        assert TRACE_ID_HEADER not in seen["headers"]
        assert TRACE_ID_HEADER.lower() not in seen["headers"]

    def test_constructor_default_trace_id_sent(self) -> None:
        seen: dict[str, Any] = {}

        def responder(request: httpx.Request) -> httpx.Response:
            seen["headers"] = dict(request.headers)
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": "x", "result": {}})

        with _client(responder, trace_id="trace-default-1") as c:
            c.send_message(Message(message_id="m", role=Role.USER, parts=[Part(text="hi")]))

        # httpx normalizes headers to lowercase keys.
        assert seen["headers"][TRACE_ID_HEADER.lower()] == "trace-default-1"

    def test_per_call_trace_id_overrides_default(self) -> None:
        seen: dict[str, Any] = {}

        def responder(request: httpx.Request) -> httpx.Response:
            seen["headers"] = dict(request.headers)
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": "x", "result": {}})

        with _client(responder, trace_id="trace-default") as c:
            c.send_message(
                Message(message_id="m", role=Role.USER, parts=[Part(text="hi")]),
                trace_id="trace-per-call",
            )

        assert seen["headers"][TRACE_ID_HEADER.lower()] == "trace-per-call"

    def test_get_task_carries_trace_id(self) -> None:
        seen: dict[str, Any] = {}

        def responder(request: httpx.Request) -> httpx.Response:
            seen["headers"] = dict(request.headers)
            return httpx.Response(
                200, json={"jsonrpc": "2.0", "id": "x", "result": {"id": "t"}},
            )

        with _client(responder) as c:
            c.get_task("TASK-1", trace_id="trace-getx")

        assert seen["headers"][TRACE_ID_HEADER.lower()] == "trace-getx"


class _EchoTraceHandler(MethodHandler):
    """들어온 trace_id 를 그대로 응답으로 돌려주는 테스트용 핸들러."""

    method_name = "EchoTrace"

    async def handle(self, request: Request, rpc_id: Any, params: dict[str, Any]):
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {"trace_id": request.state.trace_id},
            },
        )


def _make_app() -> FastAPI:
    app = FastAPI()
    app.state.agent_card = type("Card", (), {"model_dump": lambda self, **_: {}})()
    app.include_router(make_a2a_router(assistant_id="peer", handlers=[_EchoTraceHandler()]))
    return app


class TestServerReadsTraceHeader:
    @pytest.mark.asyncio
    async def test_header_passed_to_request_state(self) -> None:
        app = _make_app()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://t",
        ) as c:
            r = await c.post(
                "/a2a/peer",
                json={"jsonrpc": "2.0", "id": 1, "method": "EchoTrace", "params": {}},
                headers={TRACE_ID_HEADER: "incoming-trace-7"},
            )
        assert r.status_code == 200
        assert r.json()["result"]["trace_id"] == "incoming-trace-7"

    @pytest.mark.asyncio
    async def test_missing_header_fallback_to_new_uuid(self) -> None:
        app = _make_app()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://t",
        ) as c:
            r = await c.post(
                "/a2a/peer",
                json={"jsonrpc": "2.0", "id": 1, "method": "EchoTrace", "params": {}},
            )
        body = r.json()
        trace = body["result"]["trace_id"]
        # UUID4 형태 확인
        assert isinstance(trace, str)
        assert len(trace) == 36 and trace.count("-") == 4

    @pytest.mark.asyncio
    async def test_two_calls_without_header_get_distinct_trace_ids(self) -> None:
        app = _make_app()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://t",
        ) as c:
            r1 = await c.post(
                "/a2a/peer",
                json={"jsonrpc": "2.0", "id": 1, "method": "EchoTrace", "params": {}},
            )
            r2 = await c.post(
                "/a2a/peer",
                json={"jsonrpc": "2.0", "id": 2, "method": "EchoTrace", "params": {}},
            )
        assert r1.json()["result"]["trace_id"] != r2.json()["result"]["trace_id"]


