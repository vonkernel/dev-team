"""EventHandler 단위 테스트 — Document DB MCP 클라이언트 mock."""

from __future__ import annotations

import json
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from chronicler.handler import EventHandler
from dev_team_shared.event_bus.events import (
    ItemAppendEvent,
    SessionEndEvent,
    SessionStartEvent,
)


def _mcp_response(payload: Any) -> MagicMock:
    """FastMCP 의 CallToolResult 모킹 — content[0].text 가 JSON 직렬."""
    mock = MagicMock()
    mock.isError = False
    content = MagicMock()
    content.text = json.dumps(payload) if payload is not None else "null"
    mock.content = [content]
    return mock


class TestSessionStart:
    @pytest.mark.asyncio
    async def test_creates_fallback_task_when_missing(self) -> None:
        mcp = MagicMock()
        # 호출 순서: find_by_context (None) → agent_task.create (task) → agent_session.create (session)
        responses = [
            _mcp_response(None),  # find_by_context
            _mcp_response({"id": str(uuid.uuid4())}),  # agent_task.create
            _mcp_response({"id": str(uuid.uuid4())}),  # agent_session.create
        ]
        mcp.call_tool = AsyncMock(side_effect=responses)
        handler = EventHandler(mcp)
        await handler.handle(SessionStartEvent(
            context_id="ctx-1", initiator="user", counterpart="primary",
        ))
        # 3 calls: find / task.create / session.create
        assert mcp.call_tool.call_count == 3
        names = [c.args[0] for c in mcp.call_tool.call_args_list]
        assert names == [
            "agent_session.find_by_context",
            "agent_task.create",
            "agent_session.create",
        ]

    @pytest.mark.asyncio
    async def test_skip_when_session_exists(self) -> None:
        mcp = MagicMock()
        mcp.call_tool = AsyncMock(return_value=_mcp_response(
            {"id": str(uuid.uuid4()), "context_id": "ctx-1"},
        ))
        handler = EventHandler(mcp)
        await handler.handle(SessionStartEvent(
            context_id="ctx-1", initiator="user", counterpart="primary",
        ))
        # find_by_context 만 호출되고 끝
        assert mcp.call_tool.call_count == 1
        assert mcp.call_tool.call_args.args[0] == "agent_session.find_by_context"

    @pytest.mark.asyncio
    async def test_uses_provided_task_id(self) -> None:
        task_id = uuid.uuid4()
        mcp = MagicMock()
        mcp.call_tool = AsyncMock(side_effect=[
            _mcp_response(None),  # find_by_context
            _mcp_response({"id": str(uuid.uuid4())}),  # session.create
        ])
        handler = EventHandler(mcp)
        await handler.handle(SessionStartEvent(
            context_id="ctx-1",
            initiator="user", counterpart="primary",
            agent_task_id=task_id,
        ))
        # task.create 가 안 불려야 함 (provided id 사용)
        names = [c.args[0] for c in mcp.call_tool.call_args_list]
        assert names == [
            "agent_session.find_by_context",
            "agent_session.create",
        ]
        # session.create 의 doc.agent_task_id 가 우리가 준 task_id
        session_args = mcp.call_tool.call_args_list[1].args[1]
        assert session_args["doc"]["agent_task_id"] == str(task_id)


class TestItemAppend:
    @pytest.mark.asyncio
    async def test_skip_duplicate_message_id(self) -> None:
        sid = str(uuid.uuid4())
        mcp = MagicMock()
        mcp.call_tool = AsyncMock(side_effect=[
            _mcp_response({"id": sid, "context_id": "c"}),    # find_by_context
            _mcp_response([{"id": str(uuid.uuid4()), "message_id": "m1"}]),  # list — 이미 있음
        ])
        handler = EventHandler(mcp)
        await handler.handle(ItemAppendEvent(
            context_id="c", initiator="user", counterpart="primary",
            role="user", sender="user",
            content={"text": "hi"}, message_id="m1",
        ))
        names = [c.args[0] for c in mcp.call_tool.call_args_list]
        assert "agent_item.create" not in names


class TestSessionEnd:
    @pytest.mark.asyncio
    async def test_updates_ended_at(self) -> None:
        sid = str(uuid.uuid4())
        mcp = MagicMock()
        mcp.call_tool = AsyncMock(side_effect=[
            _mcp_response({"id": sid, "context_id": "c", "metadata": {}}),
            _mcp_response({"id": sid}),  # update
        ])
        handler = EventHandler(mcp)
        await handler.handle(SessionEndEvent(
            context_id="c", initiator="user", counterpart="primary",
            reason="completed", duration_ms=42,
        ))
        # 두 번째 호출이 agent_session.update
        update_call = mcp.call_tool.call_args_list[1]
        assert update_call.args[0] == "agent_session.update"
        patch = update_call.args[1]["patch"]
        assert patch["ended_at"] is not None
        assert patch["metadata"]["end_reason"] == "completed"
        assert patch["metadata"]["duration_ms"] == 42
