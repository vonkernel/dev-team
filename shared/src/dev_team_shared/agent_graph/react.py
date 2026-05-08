"""ReAct 패턴 building blocks — 모든 ReAct 에이전트 공유.

각 agent 의 graph.py 가 본 모듈의 factory 들을 import 해 자기 그래프를 조립.
agent 별 차이는:
- persona text (config/base.yaml)
- tools 구성 (각 agent 의 tools.py / tools/)
- topology 추가 노드 (필요 시 — graph.py 에서 add_node)

흐름 예 (Primary 같이 classify_response 추가):
    START → llm_call → (tool_calls? → tools → llm_call | done → classify_response → END)

흐름 예 (Librarian 같이 단순 ReAct):
    START → llm_call → (tool_calls? → tools → llm_call | done → END)

제공:
- `make_llm_call_node(persona, llm_with_tools)` — persona + messages → LLM
- `make_tool_node(tools)` — tool_calls 실행 → ToolMessage 들
- `should_continue_react(state, *, when_done)` — tool_calls 분기 helper
- `serialize_tool_result(value)` — tool 결과 → JSON 직렬화

사용 예:
```
from dev_team_shared.a2a import make_classify_response_node
from dev_team_shared.agent_graph import (
    make_llm_call_node, make_tool_node, should_continue_react,
)

llm_with_tools = llm.bind_tools(tools) if tools else llm

builder = StateGraph(State)
builder.add_node("llm_call", make_llm_call_node(persona, llm_with_tools))
builder.add_node("tools", make_tool_node(tools))
builder.add_node("classify_response", make_classify_response_node(llm))

builder.add_edge(START, "llm_call")
builder.add_conditional_edges(
    "llm_call",
    lambda s: should_continue_react(s, when_done="classify_response"),
    {"tools": "tools", "classify_response": "classify_response"},
)
builder.add_edge("tools", "llm_call")
builder.add_edge("classify_response", END)
```
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AnyMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)


# LangGraph 노드 시그니처 — state dict → 부분 update dict (async).
NodeFn = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


def make_llm_call_node(persona: str, llm_with_tools: BaseChatModel) -> NodeFn:
    """persona + 누적 messages → LLM (with bind_tools) 호출 노드.

    호출 실패 시:
    - 서버 로그에 full traceback (`logger.exception`)
    - 예외 원인을 풍부하게 감싼 `RuntimeError` 로 re-raise
    - 흔한 운영 이슈 (Anthropic 크레딧 부족) 에 빌링 콘솔 힌트 덧붙임

    Args:
        persona: SystemMessage content. agent 정체성 텍스트 (config/base.yaml).
        llm_with_tools: 이미 `bind_tools` 가 적용된 BaseChatModel. tools 가
            없는 agent 는 그냥 LLM 그대로 전달.
    """

    async def _llm_call(state: dict[str, Any]) -> dict[str, Any]:
        system = SystemMessage(content=persona)
        messages = state.get("messages") or []
        try:
            response = await llm_with_tools.ainvoke([system, *messages])
        except Exception as exc:
            logger.exception("LLM call failed in `llm_call` node")
            detail = f"{type(exc).__name__}: {exc}"
            if "credit balance" in str(exc).lower():
                detail += (
                    " — Anthropic 크레딧 부족 가능성. "
                    "https://console.anthropic.com/settings/billing 확인."
                )
            raise RuntimeError(f"LLM call failed — {detail}") from exc
        return {"messages": [response]}

    return _llm_call


def make_tool_node(tools: list[BaseTool]) -> NodeFn:
    """직전 AIMessage 의 `tool_calls` 를 실행해 ToolMessage 로 반환하는 노드.

    `langgraph.prebuilt.ToolNode` 와 등가. 직접 구현 — prebuilt 의존 회피 +
    동작 명시 (디버깅 용이). 알 수 없는 tool 이나 호출 실패는 ToolMessage
    안에 에러 텍스트로 담아 다음 라운드 LLM 이 보게 함 (자가 복구 기회).
    """
    tools_by_name = {t.name: t for t in tools}

    async def _tools(state: dict[str, Any]) -> dict[str, Any]:
        messages = state.get("messages") or []
        if not messages:
            return {"messages": []}
        last = messages[-1]
        tool_calls = getattr(last, "tool_calls", None) or []
        if not tool_calls:
            return {"messages": []}

        outputs: list[AnyMessage] = []
        for tc in tool_calls:
            name = tc.get("name") or ""
            tool = tools_by_name.get(name)
            tc_id = tc.get("id") or ""
            if tool is None:
                outputs.append(
                    ToolMessage(
                        content=f"unknown tool: {name!r}",
                        tool_call_id=tc_id,
                        name=name,
                    ),
                )
                continue
            try:
                result = await tool.ainvoke(tc.get("args") or {})
            except Exception as exc:
                logger.exception("tool %r raised", name)
                outputs.append(
                    ToolMessage(
                        content=f"tool error ({type(exc).__name__}): {exc}",
                        tool_call_id=tc_id,
                        name=name,
                    ),
                )
                continue
            outputs.append(
                ToolMessage(
                    content=serialize_tool_result(result),
                    tool_call_id=tc_id,
                    name=name,
                ),
            )
        return {"messages": outputs}

    return _tools


def should_continue_react(state: dict[str, Any], *, when_done: str) -> str:
    """ReAct 분기 helper — `tool_calls` 있으면 'tools', 없으면 `when_done`.

    `when_done` 은 tool 호출 끝난 뒤 갈 노드 이름 (예: `END` 또는
    `"classify_response"`). conditional edge 의 분기 key 와 일치해야 함.
    """
    messages = state.get("messages") or []
    if not messages:
        return when_done
    last = messages[-1]
    tool_calls = getattr(last, "tool_calls", None) or []
    return "tools" if tool_calls else when_done


def serialize_tool_result(value: Any) -> str:
    """tool 결과를 ToolMessage.content (str) 로 직렬화.

    Pydantic 모델 → `model_dump(mode='json')` 후 JSON. list / scalar / None 도 동일.
    LLM 이 다음 라운드에서 결과를 읽기 위해 안정적인 JSON 형태가 필요.
    """
    if value is None:
        return "null"
    if hasattr(value, "model_dump"):
        return json.dumps(value.model_dump(mode="json"), ensure_ascii=False)
    if isinstance(value, list):
        return json.dumps(
            [v.model_dump(mode="json") if hasattr(v, "model_dump") else v for v in value],
            ensure_ascii=False,
        )
    if isinstance(value, (dict, str, int, float, bool)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


__all__ = [
    "NodeFn",
    "make_llm_call_node",
    "make_tool_node",
    "serialize_tool_result",
    "should_continue_react",
]
