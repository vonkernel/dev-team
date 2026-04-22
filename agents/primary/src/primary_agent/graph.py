"""Primary 에이전트 LangGraph 그래프.

M2 스코프: 수신 → LLM 호출 → 응답 최소 흐름.
외부 MCP / Librarian / 다른 에이전트 연동 없음 (Issue #6 참조).

- 상태 키 `messages` 단일 — A2A text parts 와 호환 (docs/agent-runtime.md §5).
- 설정 경로는 패키지 위치 기준 고정 (env 변수 미사용).
  - base: agents/primary/config/base.yaml
  - override: agents/primary/config/override.yaml (선택, 없으면 skip)
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, TypedDict

from dev_team_shared.adapters.llm import LLMSpec, create_chat_model
from dev_team_shared.config_loader import load_config
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AnyMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

# 패키지 위치 기준 고정 경로:
# graph.py = agents/primary/src/primary_agent/graph.py  → parents[2] = agents/primary/
_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
_BASE_CONFIG_PATH = _PACKAGE_ROOT / "config" / "base.yaml"
_OVERRIDE_CONFIG_PATH = _PACKAGE_ROOT / "config" / "override.yaml"


class State(TypedDict):
    """LangGraph 상태. A2A 호환을 위해 `messages` 키 단일 보유."""

    messages: Annotated[list[AnyMessage], add_messages]


def _load_runtime() -> tuple[str, BaseChatModel]:
    """Role Config 를 로드해 (persona, 초기화된 LLM) 튜플을 반환."""
    config = load_config(_BASE_CONFIG_PATH, _OVERRIDE_CONFIG_PATH)

    persona = config.get("persona")
    if not persona:
        raise RuntimeError(f"config.persona is required (base: {_BASE_CONFIG_PATH})")

    llm_cfg = config.get("llm")
    if not llm_cfg:
        raise RuntimeError(f"config.llm is required (base: {_BASE_CONFIG_PATH})")

    spec = LLMSpec.from_config(llm_cfg)
    return persona, create_chat_model(spec)


# 모듈 임포트 시점에 1회만 로드. 매 호출마다 재파싱하지 않는다.
_PERSONA, _LLM = _load_runtime()


async def _llm_call(state: State) -> dict[str, list[AnyMessage]]:
    """Persona(system) + 누적 메시지를 LLM 에 전달, 응답 1개를 append."""
    system = SystemMessage(content=_PERSONA)
    response = await _LLM.ainvoke([system, *state["messages"]])
    return {"messages": [response]}


def _build() -> Any:
    builder = StateGraph(State)
    builder.add_node("llm_call", _llm_call)
    builder.add_edge(START, "llm_call")
    builder.add_edge("llm_call", END)
    return builder.compile()


graph = _build()

__all__ = ["State", "graph"]
