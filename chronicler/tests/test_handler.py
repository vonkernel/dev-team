"""EventHandler + Processors 단위 테스트."""

from __future__ import annotations

import json
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from chronicler.handler import EventHandler
from chronicler.processors import ALL_PROCESSORS, EventProcessor
from chronicler.processors.session_start import SessionStartProcessor
from chronicler.processors.item_append import ItemAppendProcessor
from chronicler.processors.session_end import SessionEndProcessor
from dev_team_shared.event_bus.events import (
    A2AEvent,
    ItemAppendEvent,
    SessionEndEvent,
    SessionStartEvent,
)
from dev_team_shared.mcp_client import StreamableMCPClient


def _mcp_response(payload: Any) -> MagicMock:
    """FastMCP 의 CallToolResult 모킹 — content[0].text 가 JSON 직렬."""
    mock = MagicMock()
    mock.isError = False
    content = MagicMock()
    content.text = json.dumps(payload) if payload is not None else "null"
    mock.content = [content]
    return mock


def _make_handler(mcp_mock: MagicMock) -> EventHandler:
    return EventHandler(ALL_PROCESSORS, mcp_mock)


# ─────────────────────────────────────────────────────────────────────────────
#  Registry / dispatch (handler.py 자체)
# ─────────────────────────────────────────────────────────────────────────────


class TestEventHandlerRegistry:
    def test_registers_all_default_processors(self) -> None:
        h = _make_handler(MagicMock())
        types = h.registered_event_types
        assert SessionStartEvent in types
        assert ItemAppendEvent in types
        assert SessionEndEvent in types

    def test_duplicate_registration_raises(self) -> None:
        class DupeProc(EventProcessor):
            event_type = SessionStartEvent
            async def process(self, event, mcp) -> None: ...

        with pytest.raises(ValueError, match="duplicate"):
            EventHandler(
                [SessionStartProcessor(), DupeProc()], MagicMock(),
            )

    @pytest.mark.asyncio
    async def test_unknown_event_type_skip(self) -> None:
        # SessionStartProcessor 만 등록 → SessionEndEvent 는 unknown
        # handle 은 raise 없이 warn 만
        h = EventHandler([SessionStartProcessor()], MagicMock())
        ev = SessionEndEvent(
            context_id="c", initiator="user", counterpart="primary",
            reason="completed",
        )
        await h.handle(ev)  # 예외 없이 끝나야 함


# ─────────────────────────────────────────────────────────────────────────────
#  SessionStartProcessor
# ─────────────────────────────────────────────────────────────────────────────


class TestSessionStartProcessor:
    @pytest.mark.asyncio
    async def test_creates_fallback_task_when_missing(self) -> None:
        mcp = MagicMock()
        mcp.call_tool = AsyncMock(side_effect=[
            _mcp_response(None),                           # find_by_context
            _mcp_response({"id": str(uuid.uuid4())}),      # agent_task.create
            _mcp_response({"id": str(uuid.uuid4())}),      # agent_session.create
        ])
        handler = _make_handler(mcp)
        await handler.handle(SessionStartEvent(
            context_id="ctx-1", initiator="user", counterpart="primary",
        ))
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
        handler = _make_handler(mcp)
        await handler.handle(SessionStartEvent(
            context_id="ctx-1", initiator="user", counterpart="primary",
        ))
        assert mcp.call_tool.call_count == 1
        assert mcp.call_tool.call_args.args[0] == "agent_session.find_by_context"

    @pytest.mark.asyncio
    async def test_uses_provided_task_id(self) -> None:
        task_id = uuid.uuid4()
        mcp = MagicMock()
        mcp.call_tool = AsyncMock(side_effect=[
            _mcp_response(None),
            _mcp_response({"id": str(uuid.uuid4())}),
        ])
        handler = _make_handler(mcp)
        await handler.handle(SessionStartEvent(
            context_id="ctx-1",
            initiator="user", counterpart="primary",
            agent_task_id=task_id,
        ))
        names = [c.args[0] for c in mcp.call_tool.call_args_list]
        assert names == [
            "agent_session.find_by_context",
            "agent_session.create",
        ]
        session_args = mcp.call_tool.call_args_list[1].args[1]
        assert session_args["doc"]["agent_task_id"] == str(task_id)


# ─────────────────────────────────────────────────────────────────────────────
#  ItemAppendProcessor
# ─────────────────────────────────────────────────────────────────────────────


class TestItemAppendProcessor:
    @pytest.mark.asyncio
    async def test_skip_duplicate_message_id(self) -> None:
        sid = str(uuid.uuid4())
        mcp = MagicMock()
        mcp.call_tool = AsyncMock(side_effect=[
            _mcp_response({"id": sid, "context_id": "c"}),  # find_by_context
            _mcp_response([{"id": str(uuid.uuid4()), "message_id": "m1"}]),  # list — 이미 있음
        ])
        handler = _make_handler(mcp)
        await handler.handle(ItemAppendEvent(
            context_id="c", initiator="user", counterpart="primary",
            role="user", sender="user",
            content={"text": "hi"}, message_id="m1",
        ))
        names = [c.args[0] for c in mcp.call_tool.call_args_list]
        assert "agent_item.create" not in names


# ─────────────────────────────────────────────────────────────────────────────
#  SessionEndProcessor
# ─────────────────────────────────────────────────────────────────────────────


class TestSessionEndProcessor:
    @pytest.mark.asyncio
    async def test_updates_ended_at(self) -> None:
        sid = str(uuid.uuid4())
        mcp = MagicMock()
        mcp.call_tool = AsyncMock(side_effect=[
            _mcp_response({"id": sid, "context_id": "c", "metadata": {}}),
            _mcp_response({"id": sid}),
        ])
        handler = _make_handler(mcp)
        await handler.handle(SessionEndEvent(
            context_id="c", initiator="user", counterpart="primary",
            reason="completed", duration_ms=42,
        ))
        update_call = mcp.call_tool.call_args_list[1]
        assert update_call.args[0] == "agent_session.update"
        patch = update_call.args[1]["patch"]
        assert patch["ended_at"] is not None
        assert patch["metadata"]["end_reason"] == "completed"
        assert patch["metadata"]["duration_ms"] == 42
