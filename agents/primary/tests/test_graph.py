"""build_graph + 그래프 헬퍼 단위 테스트.

Librarian 패턴 — `_serialize` / `_should_continue` / `_make_tool_node` 단위
테스트 중심. 전체 그래프 통합은 verify_sandbox.sh / E2E 에서 실 LLM + MCP
로 검증.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from pydantic import BaseModel

from primary_agent.graph import (
    END,
    _make_tool_node,
    _serialize,
    _should_continue,
    build_graph,
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
        ai = AIMessage(
            content="",
            tool_calls=[{"name": "x", "args": {}, "id": "tc-1"}],
        )
        assert _should_continue({"messages": [HumanMessage(content="hi"), ai]}) == "tools"

    def test_no_tool_calls(self) -> None:
        ai = AIMessage(content="응답")
        assert _should_continue({"messages": [HumanMessage(content="hi"), ai]}) == END


# ----------------------------------------------------------------------
# _make_tool_node
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tool_node_executes_tool_calls() -> None:
    from langchain_core.tools import tool

    @tool
    async def my_tool(text: str) -> str:
        """Echo."""
        return f"got: {text}"

    node = _make_tool_node([my_tool])
    ai = AIMessage(
        content="",
        tool_calls=[{"name": "my_tool", "args": {"text": "hi"}, "id": "tc-1"}],
    )
    result = await node({"messages": [HumanMessage(content="x"), ai]})
    msgs = result["messages"]
    assert len(msgs) == 1
    assert isinstance(msgs[0], ToolMessage)
    assert "got: hi" in msgs[0].content


@pytest.mark.asyncio
async def test_tool_node_unknown_tool_returns_error_message() -> None:
    node = _make_tool_node([])
    ai = AIMessage(
        content="",
        tool_calls=[{"name": "missing_tool", "args": {}, "id": "tc-1"}],
    )
    result = await node({"messages": [HumanMessage(content="x"), ai]})
    msgs = result["messages"]
    assert len(msgs) == 1
    assert "unknown tool" in msgs[0].content


@pytest.mark.asyncio
async def test_tool_node_tool_exception_captured() -> None:
    from langchain_core.tools import tool

    @tool
    async def boom(x: int) -> int:
        """raise."""
        raise ValueError("bad input")

    node = _make_tool_node([boom])
    ai = AIMessage(
        content="",
        tool_calls=[{"name": "boom", "args": {"x": 1}, "id": "tc-1"}],
    )
    result = await node({"messages": [HumanMessage(content="x"), ai]})
    msgs = result["messages"]
    assert len(msgs) == 1
    assert "tool error" in msgs[0].content
    assert "bad input" in msgs[0].content


@pytest.mark.asyncio
async def test_tool_node_no_tool_calls_returns_empty() -> None:
    node = _make_tool_node([])
    ai = AIMessage(content="자연어 응답")
    result = await node({"messages": [HumanMessage(content="x"), ai]})
    assert result == {"messages": []}


# ----------------------------------------------------------------------
# build_graph — 컴파일 검증 (실 LLM 호출은 verify_sandbox / E2E)
# ----------------------------------------------------------------------


def test_build_graph_with_tools_compiles() -> None:
    """tools 가 있으면 ReAct 그래프 컴파일."""
    from langchain_core.tools import tool

    @tool
    async def some_tool(x: str) -> str:
        """noop."""
        return x

    # bind_tools 를 mock 한 LLM (실 LLM 호출은 별도 검증).
    llm = MagicMock()
    llm.bind_tools = MagicMock(return_value=llm)
    graph = build_graph(persona="primary", llm=llm, tools=[some_tool])
    assert graph is not None
    llm.bind_tools.assert_called_once_with([some_tool])


def test_build_graph_without_tools_compiles_simple() -> None:
    """tools 가 빈 리스트면 단순 1-노드 그래프 (M2 호환). bind_tools 호출 X."""
    llm = MagicMock()
    llm.bind_tools = MagicMock()
    graph = build_graph(persona="primary", llm=llm, tools=[])
    assert graph is not None
    llm.bind_tools.assert_not_called()
