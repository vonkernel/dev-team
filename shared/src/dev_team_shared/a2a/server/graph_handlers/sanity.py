"""Graph 진입 직전 messages tail 의 dangling 패턴 감지 + marker 추가.

Cancel / 외부 proxy timeout 등으로 LangGraph 그래프가 응답을 끝내지 못한
상태에서 다음 turn 이 시작되면 messages channel 에 다음 3 가지 잔재가 남는다:

    A. user-user adjacency      — assistant 응답 없이 user 메시지가 연속
    B. trailing ToolMessage     — tool 결과 후 닫는 AIMessage 부재
    C. trailing AIMessage(tool_calls) without matching ToolMessage(s)
                                  — Anthropic API 의 tool_use → tool_result
                                    형식 검사에서 거부됨 (실패 hard-fail)

본 모듈은 graph 호출 직전에 latest checkpoint 의 messages tail 을 보고,
각 패턴에 대해 명시 marker 메시지를 append 한다. tail-only 검사 — 매 turn
시작 시 호출하면 mid-history 까지 누적될 수 없다 (turn 마다 정리되므로).

핸들러 (`send_message`, `send_streaming`) 가 graph 호출 직전에
`apply_tail_sanity(graph, config)` 를 호출.

Pattern 분류:
- A 는 LLM tolerable 하지만 의미 차이를 나타낼 SystemMessage marker 추가.
- B 는 LLM 이 dangling tool result 를 어떻게 다룰지 알도록 placeholder
  AIMessage 추가.
- C 는 **API 차원 hard 요구사항** — placeholder ToolMessage 가 없으면 LLM
  호출 자체가 실패. 본 모듈의 가장 critical 한 책임.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

logger = logging.getLogger(__name__)

USER_DANGLING_MARKER = (
    "[직전 turn 의 응답이 도중에 중단되어, 위 사용자 발화가 응답 없이 누적됨. "
    "다음 발화와 함께 종합해 응답하라.]"
)
TOOL_RESULT_DANGLING_MARKER = (
    "[직전 turn 의 응답이 도구 결과 후 중단됨. 다음 발화에 응답할 때 이 결과를 "
    "반영하라.]"
)
TOOL_CALL_INTERRUPTED = "[tool call interrupted before completion]"


def detect_tail_markers(msgs: list[AnyMessage]) -> list[AnyMessage]:
    """tail dangling 패턴을 감지해 append 할 marker 메시지 목록 반환.

    호출자는 결과를 graph state 의 messages channel 에 append 한 뒤 새 user
    입력을 invoke. marker 가 새 입력 앞에 위치해 LLM context 형태가 정상화.

    빈 목록 반환 = tail 깨끗 (또는 첫 turn).
    """
    if not msgs:
        return []
    last = msgs[-1]

    if isinstance(last, HumanMessage):
        # Pattern A: 직전이 또 HumanMessage 이면 user-user adjacency.
        # 단일 trailing HumanMessage 는 정상 (이번 turn 의 입력 — 다만 본
        # 헬퍼는 graph 호출 직전 호출되므로 실제로는 있을 수 없는 형태).
        if len(msgs) >= 2 and isinstance(msgs[-2], HumanMessage):
            return [SystemMessage(content=USER_DANGLING_MARKER)]
        return []

    if isinstance(last, ToolMessage):
        # Pattern B: tool 결과 직후 cancel — 닫는 AIMessage 부재.
        return [AIMessage(content=TOOL_RESULT_DANGLING_MARKER)]

    if isinstance(last, AIMessage) and last.tool_calls:
        # Pattern C: tool_calls 결정 직후 cancel — ToolMessage 부재.
        # tail 의 AIMessage 의 모든 tool_call 이 unanswered (정상 이라면 그
        # 직후에 ToolMessage 들이 와야 하므로). 각각에 placeholder 생성.
        return [
            ToolMessage(
                content=TOOL_CALL_INTERRUPTED,
                tool_call_id=tc.get("id", ""),
                name=tc.get("name", ""),
            )
            for tc in last.tool_calls
        ]

    # 정상 AIMessage tail (자연어 응답 완료) — 정리할 게 없음.
    return []


async def apply_tail_sanity(graph: Any, config: dict[str, Any]) -> int:
    """Graph 의 latest checkpoint 에 sanity marker 를 append.

    Args:
        graph: CompiledStateGraph (`aget_state` / `aupdate_state` 지원).
        config: `{"configurable": {"thread_id": ...}}`.

    Returns:
        추가된 marker 개수. 0 이면 깨끗 (또는 첫 turn).
    """
    state = await graph.aget_state(config)
    if state is None or not state.values:
        return 0
    msgs = state.values.get("messages") or []
    markers = detect_tail_markers(msgs)
    if not markers:
        return 0
    await graph.aupdate_state(config, {"messages": markers})
    logger.info(
        "graph_sanity.tail_markers_applied thread_id=%s count=%d patterns=%s",
        config.get("configurable", {}).get("thread_id"),
        len(markers),
        [type(m).__name__ for m in markers],
    )
    return len(markers)


__all__ = [
    "TOOL_CALL_INTERRUPTED",
    "TOOL_RESULT_DANGLING_MARKER",
    "USER_DANGLING_MARKER",
    "apply_tail_sanity",
    "detect_tail_markers",
]
