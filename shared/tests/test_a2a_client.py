"""A2A 클라이언트 단위 테스트.

실제 HTTP 엔드포인트를 띄우지 않고 `httpx.MockTransport` 로 요청을 인터셉트한다.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from dev_team_shared.a2a import A2AClient, A2AClientError
from dev_team_shared.a2a.types import Message, Part, Role


def _mock_transport(responder) -> httpx.MockTransport:  # type: ignore[no-untyped-def]
    return httpx.MockTransport(responder)


def _build_client(responder, *, method_style="pascal") -> A2AClient:  # type: ignore[no-untyped-def]
    transport = _mock_transport(responder)
    http = httpx.Client(transport=transport)
    return A2AClient(
        "http://architect:9000/a2a/architect",
        method_style=method_style,
        http_client=http,
    )


class TestSendMessage:
    def test_pascal_method_name_is_used(self) -> None:
        seen: dict[str, Any] = {}

        def responder(request: httpx.Request) -> httpx.Response:
            seen["body"] = json.loads(request.content)
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": "x", "result": {"ok": True}})

        with _build_client(responder) as client:
            msg = Message(
                message_id="ITM-1",
                role=Role.USER,
                parts=[Part(text="hello", media_type="text/plain")],
            )
            result = client.send_message(msg)

        assert seen["body"]["method"] == "SendMessage"
        assert result == {"ok": True}

    def test_slash_method_name_for_legacy_servers(self) -> None:
        seen: dict[str, Any] = {}

        def responder(request: httpx.Request) -> httpx.Response:
            seen["body"] = json.loads(request.content)
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": "x", "result": {"ok": True}})

        with _build_client(responder, method_style="slash") as client:
            msg = Message(
                message_id="ITM-1",
                role=Role.USER,
                parts=[Part(text="hi")],
            )
            client.send_message(msg)

        assert seen["body"]["method"] == "message/send"

    def test_message_serializes_as_camelcase_with_enum_strings(self) -> None:
        seen: dict[str, Any] = {}

        def responder(request: httpx.Request) -> httpx.Response:
            seen["body"] = json.loads(request.content)
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": "x", "result": {}})

        with _build_client(responder) as client:
            msg = Message(
                message_id="ITM-42",
                role=Role.USER,
                parts=[Part(text="hi", media_type="text/plain")],
                context_id="SES-xxx",
                task_id="TASK-001",
            )
            client.send_message(msg)

        params = seen["body"]["params"]["message"]
        # camelCase
        assert "messageId" in params
        assert "contextId" in params
        assert "taskId" in params
        # enum 은 SCREAMING_SNAKE_CASE 문자열 그대로
        assert params["role"] == "ROLE_USER"
        # Part 도 camelCase
        assert params["parts"][0]["mediaType"] == "text/plain"

    def test_error_response_raises(self) -> None:
        def responder(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": "x",
                    "error": {"code": -32601, "message": "method not found"},
                },
            )

        with _build_client(responder) as client:
            msg = Message(message_id="ITM-1", role=Role.USER, parts=[Part(text="x")])
            with pytest.raises(A2AClientError) as exc_info:
                client.send_message(msg)

        assert exc_info.value.code == -32601
        assert "method not found" in str(exc_info.value)

    def test_http_error_raises(self) -> None:
        def responder(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="boom")

        with _build_client(responder) as client:
            msg = Message(message_id="ITM-1", role=Role.USER, parts=[Part(text="x")])
            with pytest.raises(A2AClientError):
                client.send_message(msg)


class TestGetTask:
    def test_method_and_params(self) -> None:
        seen: dict[str, Any] = {}

        def responder(request: httpx.Request) -> httpx.Response:
            seen["body"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": "x",
                    "result": {"id": "TASK-1", "status": {"state": "TASK_STATE_WORKING"}},
                },
            )

        with _build_client(responder) as client:
            result = client.get_task("TASK-1", history_length=10)

        body = seen["body"]
        assert body["method"] == "GetTask"
        assert body["params"] == {"taskId": "TASK-1", "historyLength": 10}
        assert result["status"]["state"] == "TASK_STATE_WORKING"
