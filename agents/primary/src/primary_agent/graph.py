"""Primary 에이전트 LangGraph 그래프.

M2 스코프: 수신 → LLM 호출 → 응답 최소 흐름.
외부 MCP / Librarian / 다른 에이전트 연동 없음 (Issue #6 참조).

- 상태에 `messages` 키 포함 — LangChain 생태계 공용 규약
  (HumanMessage/AIMessage 리스트 + `add_messages` reducer).
- 영속 체크포인팅: `build_graph(checkpointer=...)` 로 `AsyncPostgresSaver` 등
  주입 가능. 미주입 시 in-memory (재기동 시 상태 소실).
- 설정 경로는 패키지 위치 기준 고정 (env 변수 미사용).
  - base: agents/primary/config/base.yaml
  - override: agents/primary/config/override.yaml (선택, 없으면 skip)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated, Any, TypedDict

from dev_team_shared.adapters.llm import LLMSpec, create_chat_model
from dev_team_shared.config_loader import load_config
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AnyMessage, SystemMessage
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

    `messages` 키는 LangChain 생태계 공용 규약. `add_messages` reducer 가
    부분 업데이트를 append 로 누적. 이후 다른 상태 키
    (retrieved_docs, plan_steps 등) 를 추가해도 호환 유지.
    """

    messages: Annotated[list[AnyMessage], add_messages]


def load_runtime_config() -> dict[str, Any]:
    """Role Config 를 로드해 병합 · 치환된 dict 를 반환."""
    return load_config(_BASE_CONFIG_PATH, _OVERRIDE_CONFIG_PATH)


def build_llm(llm_cfg: dict[str, Any]) -> BaseChatModel:
    """llm config 섹션으로부터 초기화된 ChatModel 을 반환."""
    spec = LLMSpec.from_config(llm_cfg)
    return create_chat_model(spec)


def _make_llm_call_node(persona: str, llm: BaseChatModel):
    """persona / llm 을 클로저로 캡처한 비동기 노드 함수를 반환.

    실패 시:
    - 서버 로그에 full traceback (`logger.exception`)
    - 예외 원인을 풍부하게 감싼 `RuntimeError` 로 re-raise
    - 흔한 운영 이슈(크레딧 부족) 에 빌링 콘솔 힌트 덧붙임
    """

    async def _llm_call(state: State) -> dict[str, list[AnyMessage]]:
        system = SystemMessage(content=persona)
        try:
            response = await llm.ainvoke([system, *state["messages"]])
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


def build_graph(
    *,
    persona: str,
    llm: BaseChatModel,
    checkpointer: BaseCheckpointSaver | None = None,
) -> Any:
    """persona / llm / (선택) checkpointer 주입해 그래프를 컴파일.

    Args:
        persona: SystemMessage content 로 삽입될 정체성 문자열.
        llm: 초기화된 BaseChatModel.
        checkpointer: `AsyncPostgresSaver` 등. `None` 이면 in-memory
                      (재기동 시 상태 소실).

    Returns:
        CompiledStateGraph — `.ainvoke()` / `.astream()` 호출 가능.
    """
    builder = StateGraph(State)
    builder.add_node("llm_call", _make_llm_call_node(persona, llm))
    builder.add_edge(START, "llm_call")
    builder.add_edge("llm_call", END)
    return builder.compile(checkpointer=checkpointer)


__all__ = ["State", "build_graph", "build_llm", "load_runtime_config"]
