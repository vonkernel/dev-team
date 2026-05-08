"""Graph entry sanity (#73) 단위 테스트.

`detect_tail_markers` 의 3 가지 dangling 패턴 + 정상 tail / 빈 history 처리.
`apply_tail_sanity` 는 InMemorySaver + 작은 graph 로 통합.
"""

from __future__ import annotations

import pytest
from dev_team_shared.a2a.server.graph_handlers.sanity import (
    TOOL_CALL_INTERRUPTED,
    TOOL_RESULT_DANGLING_MARKER,
    USER_DANGLING_MARKER,
    apply_tail_sanity,
    detect_tail_markers,
)
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import Annotated, TypedDict


class _State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def _identity_node(state: _State) -> dict[str, list[AnyMessage]]:
    return {"messages": []}


def _build_graph():  # type: ignore[no-untyped-def]
    """Sanity 통합 테스트용 최소 graph (1 노드, no LLM)."""
    builder = StateGraph(_State)
    builder.add_node("identity", _identity_node)
    builder.add_edge(START, "identity")
    builder.add_edge("identity", END)
    return builder.compile(checkpointer=InMemorySaver())


# ─────────────────────────────────────────────────────────────────────────
#  detect_tail_markers — 단위
# ─────────────────────────────────────────────────────────────────────────


class TestDetectTailMarkers:
    def test_empty_returns_empty(self) -> None:
        assert detect_tail_markers([]) == []

    def test_single_user_msg_is_clean(self) -> None:
        # 첫 turn 의 입력 직후 — 정상 (단일 trailing user)
        assert detect_tail_markers([HumanMessage(content="hi")]) == []

    def test_user_user_adjacency_marker(self) -> None:
        # Pattern A: assistant 응답 누락된 채 user 가 연속
        msgs = [
            AIMessage(content="hello"),
            HumanMessage(content="첫 발화"),
            HumanMessage(content="둘째 발화 (응답 못 받음)"),
        ]
        markers = detect_tail_markers(msgs)
        assert len(markers) == 1
        assert isinstance(markers[0], SystemMessage)
        assert markers[0].content == USER_DANGLING_MARKER

    def test_user_after_ai_is_clean(self) -> None:
        # 정상: AI → User (이번 turn 의 입력)
        msgs = [
            AIMessage(content="hello"),
            HumanMessage(content="첫 발화"),
        ]
        assert detect_tail_markers(msgs) == []

    def test_trailing_tool_message_marker(self) -> None:
        # Pattern B: tool 결과 후 닫는 AI 부재
        msgs = [
            HumanMessage(content="search"),
            AIMessage(content="", tool_calls=[
                {"id": "call_1", "name": "search", "args": {}},
            ]),
            ToolMessage(content="result", tool_call_id="call_1", name="search"),
        ]
        markers = detect_tail_markers(msgs)
        assert len(markers) == 1
        assert isinstance(markers[0], AIMessage)
        assert markers[0].content == TOOL_RESULT_DANGLING_MARKER

    def test_trailing_ai_with_tool_calls_marker_per_call(self) -> None:
        # Pattern C: tool_calls 결정 직후 cancel — Anthropic API hard requirement
        msgs = [
            HumanMessage(content="do two things"),
            AIMessage(content="", tool_calls=[
                {"id": "call_a", "name": "tool_a", "args": {}},
                {"id": "call_b", "name": "tool_b", "args": {"x": 1}},
            ]),
        ]
        markers = detect_tail_markers(msgs)
        assert len(markers) == 2
        assert all(isinstance(m, ToolMessage) for m in markers)
        assert markers[0].tool_call_id == "call_a"  # type: ignore[union-attr]
        assert markers[0].name == "tool_a"  # type: ignore[union-attr]
        assert markers[0].content == TOOL_CALL_INTERRUPTED  # type: ignore[union-attr]
        assert markers[1].tool_call_id == "call_b"  # type: ignore[union-attr]
        assert markers[1].name == "tool_b"  # type: ignore[union-attr]

    def test_clean_ai_tail_returns_empty(self) -> None:
        # 정상 종료 — final AI text 응답
        msgs = [
            HumanMessage(content="안녕"),
            AIMessage(content="안녕하세요!"),
        ]
        assert detect_tail_markers(msgs) == []

    def test_ai_without_tool_calls_is_clean(self) -> None:
        # AIMessage 에 tool_calls 가 빈 목록인 경우도 정상으로 본다
        msgs = [
            HumanMessage(content="hi"),
            AIMessage(content="hello", tool_calls=[]),
        ]
        assert detect_tail_markers(msgs) == []


# ─────────────────────────────────────────────────────────────────────────
#  apply_tail_sanity — 통합 (InMemorySaver)
# ─────────────────────────────────────────────────────────────────────────


class TestApplyTailSanity:
    @pytest.mark.asyncio
    async def test_no_state_is_noop(self) -> None:
        graph = _build_graph()
        config = {"configurable": {"thread_id": "fresh-thread"}}
        n = await apply_tail_sanity(graph, config)
        assert n == 0

    @pytest.mark.asyncio
    async def test_clean_state_is_noop(self) -> None:
        graph = _build_graph()
        config = {"configurable": {"thread_id": "clean-thread"}}
        # 1 turn 정상 진행
        await graph.ainvoke(
            {"messages": [HumanMessage(content="hi"), AIMessage(content="hello")]},
            config=config,
        )
        n = await apply_tail_sanity(graph, config)
        assert n == 0

    @pytest.mark.asyncio
    async def test_user_user_state_appends_marker(self) -> None:
        graph = _build_graph()
        config = {"configurable": {"thread_id": "user-user-thread"}}
        # dangling user-user 시뮬레이션
        await graph.ainvoke(
            {"messages": [
                AIMessage(content="hi"),
                HumanMessage(content="첫"),
                HumanMessage(content="둘째"),
            ]},
            config=config,
        )
        n = await apply_tail_sanity(graph, config)
        assert n == 1
        # 결과 state 확인
        state = await graph.aget_state(config)
        msgs = state.values["messages"]
        assert isinstance(msgs[-1], SystemMessage)
        assert msgs[-1].content == USER_DANGLING_MARKER

    @pytest.mark.asyncio
    async def test_trailing_tool_state_appends_ai_marker(self) -> None:
        graph = _build_graph()
        config = {"configurable": {"thread_id": "tool-tail-thread"}}
        await graph.ainvoke(
            {"messages": [
                HumanMessage(content="search"),
                AIMessage(content="", tool_calls=[
                    {"id": "call_1", "name": "search", "args": {}},
                ]),
                ToolMessage(content="result", tool_call_id="call_1", name="search"),
            ]},
            config=config,
        )
        n = await apply_tail_sanity(graph, config)
        assert n == 1
        state = await graph.aget_state(config)
        last = state.values["messages"][-1]
        assert isinstance(last, AIMessage)
        assert last.content == TOOL_RESULT_DANGLING_MARKER

    @pytest.mark.asyncio
    async def test_unanswered_tool_calls_appends_placeholders(self) -> None:
        graph = _build_graph()
        config = {"configurable": {"thread_id": "tool-call-thread"}}
        await graph.ainvoke(
            {"messages": [
                HumanMessage(content="do two"),
                AIMessage(content="", tool_calls=[
                    {"id": "x", "name": "tool_x", "args": {}},
                    {"id": "y", "name": "tool_y", "args": {}},
                ]),
            ]},
            config=config,
        )
        n = await apply_tail_sanity(graph, config)
        assert n == 2
        state = await graph.aget_state(config)
        msgs = state.values["messages"]
        # 마지막 두 메시지가 placeholder ToolMessage
        assert isinstance(msgs[-2], ToolMessage)
        assert isinstance(msgs[-1], ToolMessage)
        assert {msgs[-2].tool_call_id, msgs[-1].tool_call_id} == {"x", "y"}

    @pytest.mark.asyncio
    async def test_idempotent_after_apply(self) -> None:
        graph = _build_graph()
        config = {"configurable": {"thread_id": "idempotent-thread"}}
        await graph.ainvoke(
            {"messages": [
                AIMessage(content="hi"),
                HumanMessage(content="첫"),
                HumanMessage(content="둘째"),
            ]},
            config=config,
        )
        n1 = await apply_tail_sanity(graph, config)
        n2 = await apply_tail_sanity(graph, config)
        assert n1 == 1
        # 두 번째 호출은 tail 이 SystemMessage 라 dangling 패턴 아님 → no-op
        assert n2 == 0
