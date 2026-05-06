"""Librarian 의 LangGraph 그래프 — ReAct 패턴.

흐름 (mermaid):
    START → llm_call → (tool_calls 있음? → tools → llm_call) → END

- `llm_call` 노드: persona + 누적 messages → LLM (with bind_tools) → AIMessage
  · AIMessage 에 tool_calls 가 있으면 다음 라운드에서 도구 실행
  · 없으면 자연어 응답 완성 → END
- `tools` 노드: AIMessage.tool_calls 의 각 호출을 실행 → ToolMessage 들로 반환
- conditional edge `should_continue` 가 분기 결정

Primary 의 단순 1-노드 패턴 위에서 ReAct 루프 추가. langgraph.prebuilt.ToolNode
대신 직접 노드 구현 — 의존 최소 + 동작 명시.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Annotated, Any, TypedDict

from dev_team_shared.config_loader import load_config
from dev_team_shared.llm import LLMSpec, create_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AnyMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

logger = logging.getLogger(__name__)

# 패키지 위치 기준 고정 경로:
# graph.py = agents/librarian/src/librarian_agent/graph.py → parents[2] = agents/librarian/
_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
_BASE_CONFIG_PATH = _PACKAGE_ROOT / "config" / "base.yaml"
_OVERRIDE_CONFIG_PATH = _PACKAGE_ROOT / "config" / "override.yaml"


class State(TypedDict):
    """LangGraph 상태. Primary 와 동일한 messages reducer."""

    messages: Annotated[list[AnyMessage], add_messages]


def load_runtime_config() -> dict[str, Any]:
    """Role Config 로드."""
    return load_config(_BASE_CONFIG_PATH, _OVERRIDE_CONFIG_PATH)


def build_llm(llm_cfg: dict[str, Any]) -> BaseChatModel:
    spec = LLMSpec.from_config(llm_cfg)
    return create_chat_model(spec)


def _make_llm_call_node(persona: str, llm_with_tools: BaseChatModel):
    """persona / tools-bound LLM 캡처한 비동기 노드."""

    async def _llm_call(state: State) -> dict[str, list[AnyMessage]]:
        system = SystemMessage(content=persona)
        try:
            response = await llm_with_tools.ainvoke([system, *state["messages"]])
        except Exception as exc:
            logger.exception("LLM call failed in `_llm_call` node")
            detail = f"{type(exc).__name__}: {exc}"
            if "credit balance" in str(exc).lower():
                detail += (
                    " — Anthropic 크레딧 부족 가능성. "
                    "https://console.anthropic.com/settings/billing 확인."
                )
            raise RuntimeError(f"LLM call failed — {detail}") from exc
        return {"messages": [response]}

    return _llm_call


def _make_tool_node(tools: list[BaseTool]):
    """tool_calls 를 실행해 ToolMessage 들로 반환하는 노드.

    langgraph.prebuilt.ToolNode 와 등가. 직접 구현 — prebuilt 의존 회피 +
    동작 명시 (디버깅 용이).
    """
    tools_by_name = {t.name: t for t in tools}

    async def _tools(state: State) -> dict[str, list[AnyMessage]]:
        last = state["messages"][-1]
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
                    content=_serialize(result),
                    tool_call_id=tc_id,
                    name=name,
                ),
            )
        return {"messages": outputs}

    return _tools


def _should_continue(state: State) -> str:
    """tool_calls 가 있으면 'tools' 노드로, 없으면 END."""
    last = state["messages"][-1]
    tool_calls = getattr(last, "tool_calls", None) or []
    return "tools" if tool_calls else END


def _serialize(value: Any) -> str:
    """tool 결과를 ToolMessage.content (str) 로 직렬화.

    Pydantic 모델 → model_dump(mode='json') 후 JSON. list / scalar / None 도 동일.
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


def build_graph(
    *,
    persona: str,
    llm: BaseChatModel,
    tools: list[BaseTool],
    checkpointer: BaseCheckpointSaver | None = None,
) -> Any:
    """persona / llm / tools / checkpointer 주입해 ReAct 그래프 컴파일.

    Args:
        persona: SystemMessage content.
        llm: BaseChatModel (tools 와 별도 — 본 함수가 bind_tools).
        tools: LangChain tool 목록 (build_tools(client) 결과).
        checkpointer: AsyncPostgresSaver 등. None 이면 in-memory.
    """
    llm_with_tools = llm.bind_tools(tools)

    builder = StateGraph(State)
    builder.add_node("llm_call", _make_llm_call_node(persona, llm_with_tools))
    builder.add_node("tools", _make_tool_node(tools))
    builder.add_edge(START, "llm_call")
    builder.add_conditional_edges(
        "llm_call",
        _should_continue,
        {"tools": "tools", END: END},
    )
    builder.add_edge("tools", "llm_call")
    return builder.compile(checkpointer=checkpointer)


__all__ = ["State", "build_graph", "build_llm", "load_runtime_config"]
