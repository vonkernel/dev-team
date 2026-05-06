"""Librarian 그래프 헬퍼 단위 테스트 — _serialize / _should_continue / _make_tool_node."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from pydantic import BaseModel

from librarian_agent.graph import (
    END,
    _make_tool_node,
    _serialize,
    _should_continue,
)


# ----------------------------------------------------------------------
# _serialize
# ----------------------------------------------------------------------


class _Sample(BaseModel):
    a: int
    b: str


class TestSerialize:
    def test_none(self) -> None:
        assert _serialize(None) == "null"

    def test_pydantic_model(self) -> None:
        out = _serialize(_Sample(a=1, b="x"))
        assert json.loads(out) == {"a": 1, "b": "x"}

    def test_list_of_models(self) -> None:
        out = _serialize([_Sample(a=1, b="x"), _Sample(a=2, b="y")])
        assert json.loads(out) == [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]

    def test_dict(self) -> None:
        assert json.loads(_serialize({"k": "v"})) == {"k": "v"}

    def test_scalar(self) -> None:
        assert _serialize(42) == "42"
        assert _serialize(True) == "true"
        assert _serialize("hello") == '"hello"'


# ----------------------------------------------------------------------
# _should_continue
# ----------------------------------------------------------------------


class TestShouldContinue:
    def test_tool_calls_present(self) -> None:
        last = AIMessage(
            content="",
            tool_calls=[{"name": "x", "args": {}, "id": "1", "type": "tool_call"}],
        )
        state = {"messages": [HumanMessage(content="hi"), last]}
        assert _should_continue(state) == "tools"

    def test_no_tool_calls(self) -> None:
        last = AIMessage(content="응답")
        state = {"messages": [HumanMessage(content="hi"), last]}
        assert _should_continue(state) is END


# ----------------------------------------------------------------------
# _make_tool_node — 실제 tool 함수 호출 / 미존재 / 예외 모두 검증
# ----------------------------------------------------------------------


class _FakeTool:
    """LangChain BaseTool 의 최소 인터페이스 흉내 — `name` + `ainvoke`."""

    def __init__(self, name: str, return_value: Any = None, raises: Exception | None = None) -> None:
        self.name = name
        self._return = return_value
        self._raises = raises
        self.calls: list[dict] = []

    async def ainvoke(self, args: dict) -> Any:
        self.calls.append(args)
        if self._raises is not None:
            raise self._raises
        return self._return


@pytest.mark.asyncio
async def test_tool_node_executes_tool_calls() -> None:
    fake = _FakeTool("hello_tool", return_value=_Sample(a=1, b="x"))
    node = _make_tool_node([fake])  # type: ignore[arg-type]
    last = AIMessage(
        content="",
        tool_calls=[
            {"name": "hello_tool", "args": {"foo": "bar"}, "id": "tc1", "type": "tool_call"},
        ],
    )
    out = await node({"messages": [last]})
    assert fake.calls == [{"foo": "bar"}]
    assert len(out["messages"]) == 1
    msg = out["messages"][0]
    assert isinstance(msg, ToolMessage)
    assert msg.tool_call_id == "tc1"
    assert json.loads(msg.content) == {"a": 1, "b": "x"}


@pytest.mark.asyncio
async def test_tool_node_unknown_tool_returns_error_message() -> None:
    node = _make_tool_node([])
    last = AIMessage(
        content="",
        tool_calls=[
            {"name": "missing", "args": {}, "id": "tc1", "type": "tool_call"},
        ],
    )
    out = await node({"messages": [last]})
    msg = out["messages"][0]
    assert "unknown tool" in msg.content
    assert msg.tool_call_id == "tc1"


@pytest.mark.asyncio
async def test_tool_node_tool_exception_captured() -> None:
    fake = _FakeTool("boom", raises=RuntimeError("kaboom"))
    node = _make_tool_node([fake])  # type: ignore[arg-type]
    last = AIMessage(
        content="",
        tool_calls=[{"name": "boom", "args": {}, "id": "tc1", "type": "tool_call"}],
    )
    out = await node({"messages": [last]})
    msg = out["messages"][0]
    assert "tool error" in msg.content
    assert "kaboom" in msg.content


@pytest.mark.asyncio
async def test_tool_node_no_tool_calls_returns_empty() -> None:
    node = _make_tool_node([])
    last = AIMessage(content="just a response")
    out = await node({"messages": [last]})
    assert out["messages"] == []
