"""Primary 에이전트 LangGraph 그래프 — ReAct 패턴 + A2A 응답 분기 (#39, #75).

흐름 (mermaid):
    START → llm_call → (tool_calls? → tools → llm_call | done → classify_response → END)

building blocks:
- `llm_call` / `tools` / `should_continue_react` — `dev_team_shared.agent_graph` 의 ReAct 공통
- `classify_response` — `dev_team_shared.a2a` 의 A2A 응답 shape 결정 (Task wrap vs Message)

agent-specific:
- persona text — `config/base.yaml` 의 `persona`
- tools 구성 — `tools/` (4 채널: Doc Store / IssueTracker / Wiki / Librarian A2A)
- State (`messages` + `requires_task`)

설정 경로는 패키지 위치 기준 고정 (env 변수 미사용):
- base: agents/primary/config/base.yaml
- override: agents/primary/config/override.yaml (선택, 없으면 skip)
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
# graph.py = agents/primary/src/primary_agent/graph.py  → parents[2] = agents/primary/
_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
_BASE_CONFIG_PATH = _PACKAGE_ROOT / "config" / "base.yaml"
_OVERRIDE_CONFIG_PATH = _PACKAGE_ROOT / "config" / "override.yaml"


class State(TypedDict):
    """LangGraph 상태.

    `messages` — LangChain 공용 규약. `add_messages` reducer 가 부분 업데이트
    를 append 로 누적.

    `requires_task` — A2A 응답 shape 결정 (#75 PR 3). `classify_response` 노드
    가 LLM 추론으로 채움. handler 가 stream / invoke 종료 후 graph state 에서
    읽어 Task wrap / Message only 분기.

    `extra_system_message` — caller (chat handler / A2A handler) 가 매 호출
    시 주입하는 runtime context (예: 현재 chat session_id). shared/agent_graph
    의 `make_llm_call_node` 가 persona 끝에 합쳐 LLM 에 노출 → LLM 이 도구
    호출 시 (예: assignment_create) 해당 정보 활용 가능. LangGraph thread
    checkpoint 로 turn 간 자동 유지.
    """

    messages: Annotated[list[AnyMessage], add_messages]
    requires_task: NotRequired[bool]
    extra_system_message: NotRequired[str]


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
    """persona / llm / tools / (선택) checkpointer 주입해 그래프 컴파일.

    Args:
        persona: SystemMessage content 로 삽입될 정체성 문자열.
        llm: 초기화된 BaseChatModel (tools 와 별도 — 본 함수가 bind_tools).
        tools: LangChain tool 목록 (build_tools(...) 결과). 빈 리스트도 허용
               (M2 호환 — bind_tools 가 빈 목록이면 단순 LLM 호출 동등).
        checkpointer: `AsyncPostgresSaver` 등. `None` 이면 in-memory.

    Returns:
        CompiledStateGraph — `.ainvoke()` / `.astream()` 호출 가능.
    """
    llm_with_tools = llm.bind_tools(tools) if tools else llm

    builder = StateGraph(State)
    builder.add_node("llm_call", make_llm_call_node(persona, llm_with_tools))
    builder.add_node("classify_response", make_classify_response_node(llm))
    builder.add_edge(START, "llm_call")

    if tools:
        builder.add_node("tools", make_tool_node(tools))
        builder.add_conditional_edges(
            "llm_call",
            lambda s: should_continue_react(s, when_done="classify_response"),
            {"tools": "tools", "classify_response": "classify_response"},
        )
        builder.add_edge("tools", "llm_call")
    else:
        builder.add_edge("llm_call", "classify_response")

    builder.add_edge("classify_response", END)
    return builder.compile(checkpointer=checkpointer)


__all__ = ["State", "build_graph", "build_llm", "load_runtime_config"]
