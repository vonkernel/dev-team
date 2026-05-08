"""Librarian 에이전트 LangGraph 그래프 — ReAct 패턴 + A2A 응답 분기.

흐름 (mermaid):
    START → llm_call → (tool_calls? → tools → llm_call | done → classify_response → END)

building blocks:
- `llm_call` / `tools` / `should_continue_react` — `dev_team_shared.agent_graph` 의 ReAct 공통
- `classify_response` — `dev_team_shared.a2a` 의 A2A 응답 shape 결정 (Task wrap vs Message)

agent-specific:
- persona text — `config/base.yaml`
- tools 구성 — `tools.py` (Doc Store read 도구 + 조합 쿼리)
- State (`messages` + `requires_task`)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated, Any, NotRequired, TypedDict

from dev_team_shared.a2a import make_classify_response_node
from dev_team_shared.agent_graph import (
    make_llm_call_node,
    make_tool_node,
    should_continue_react,
)
from dev_team_shared.config_loader import load_config
from dev_team_shared.llm import LLMSpec, create_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AnyMessage
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
    """LangGraph 상태. Primary 와 동일 구조 (messages + A2A 응답 결정 hint)."""

    messages: Annotated[list[AnyMessage], add_messages]
    requires_task: NotRequired[bool]


def load_runtime_config() -> dict[str, Any]:
    return load_config(_BASE_CONFIG_PATH, _OVERRIDE_CONFIG_PATH)


def build_llm(llm_cfg: dict[str, Any]) -> BaseChatModel:
    spec = LLMSpec.from_config(llm_cfg)
    return create_chat_model(spec)


def build_graph(
    *,
    persona: str,
    llm: BaseChatModel,
    tools: list[BaseTool],
    checkpointer: BaseCheckpointSaver | None = None,
) -> Any:
    """persona / llm / tools / checkpointer 주입해 ReAct 그래프 컴파일."""
    llm_with_tools = llm.bind_tools(tools)

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
    return builder.compile(checkpointer=checkpointer)


__all__ = ["State", "build_graph", "build_llm", "load_runtime_config"]
