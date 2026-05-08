"""Primary 에이전트 LangGraph 그래프 — ReAct 패턴 (#39).

흐름 (mermaid):
    START → llm_call → (tool_calls 있음? → tools → llm_call) → END

- `llm_call` 노드: persona + 누적 messages → LLM (with bind_tools) → AIMessage
  · AIMessage 에 tool_calls 가 있으면 다음 라운드에서 도구 실행
  · 없으면 자연어 응답 완성 → END (사용자에게 컨펌 / 추가 입력 요청 시 자연
    스럽게 다음 사이클로 넘어감 — A2A `TASK_STATE_INPUT_REQUIRED` 매핑은
    `shared/a2a/server/graph_handlers` 책임)
- `tools` 노드: AIMessage.tool_calls 의 각 호출을 실행 → ToolMessage 들로 반환
- conditional edge `should_continue` 가 분기 결정

도구는 build_tools(...) 로 4 채널 (Doc Store / IssueTracker / Wiki /
Librarian A2A) 통합. 분담 모델은 #63 / #64 참조 — write 는 자기 도메인
(wiki_pages / issues) 직접, 정보 검색은 Librarian 위임.

설정 경로는 패키지 위치 기준 고정 (env 변수 미사용).
- base: agents/primary/config/base.yaml
- override: agents/primary/config/override.yaml (선택, 없으면 skip)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Annotated, Any, NotRequired, TypedDict

from dev_team_shared.a2a import A2AResponseDecision
from dev_team_shared.config_loader import load_config
from dev_team_shared.llm import LLMSpec, create_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
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

    `messages` 키는 LangChain 생태계 공용 규약. `add_messages` reducer 가
    부분 업데이트를 append 로 누적. 컨펌 / draft / sync 진행 상태도 messages
    안의 AIMessage / ToolMessage 로 자연스럽게 추적되므로 별도 키 추가 X
    (단순 우선 — 추후 필요 시 확장).

    `requires_task` 는 #75 PR 3 의 A2A 응답 shape 결정 — `classify_response`
    노드가 LLM 추론으로 채움. handler 가 stream / invoke 종료 후 graph state
    에서 읽어 Task wrap / Message only 분기 결정.
    """

    messages: Annotated[list[AnyMessage], add_messages]
    requires_task: NotRequired[bool]


def load_runtime_config() -> dict[str, Any]:
    """Role Config 를 로드해 병합 · 치환된 dict 를 반환."""
    return load_config(_BASE_CONFIG_PATH, _OVERRIDE_CONFIG_PATH)


def build_llm(llm_cfg: dict[str, Any]) -> BaseChatModel:
    """llm config 섹션으로부터 초기화된 ChatModel 을 반환."""
    spec = LLMSpec.from_config(llm_cfg)
    return create_chat_model(spec)


def _make_llm_call_node(persona: str, llm_with_tools: BaseChatModel):
    """persona / tools-bound LLM 캡처한 비동기 노드.

    실패 시:
    - 서버 로그에 full traceback (`logger.exception`)
    - 예외 원인을 풍부하게 감싼 `RuntimeError` 로 re-raise
    - 흔한 운영 이슈(크레딧 부족) 에 빌링 콘솔 힌트 덧붙임
    """

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
    동작 명시 (디버깅 용이). Librarian 의 graph 패턴과 동일.
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
    """tool_calls 가 있으면 'tools' 노드로, 없으면 classify_response 로."""
    last = state["messages"][-1]
    tool_calls = getattr(last, "tool_calls", None) or []
    return "tools" if tool_calls else "classify_response"


_CLASSIFY_PROMPT = (
    "You are reviewing the agent's final response to a peer agent's request "
    "(A2A inter-agent communication). Decide whether the response should be "
    "wrapped as an A2A Task or sent as a plain Message.\n\n"
    "requires_task=true when:\n"
    "  - the response delegates work to another agent or starts a long-running operation\n"
    "  - the caller will need to follow up referencing this work (track progress, fetch artifacts)\n"
    "  - stateful outputs (artifacts, status transitions) are produced or expected\n\n"
    "requires_task=false when:\n"
    "  - the response is a simple answer, opinion, or fact lookup\n"
    "  - no follow-up tracking is required by the caller\n\n"
    "Look at the final assistant message and the request that prompted it to decide."
)


def _format_conversation_for_classifier(messages: list[AnyMessage]) -> str:
    """state.messages 를 classifier 가 볼 수 있는 한 덩어리 텍스트로 직렬화.

    이유: 일부 LLM provider (Anthropic) 는 대화가 user message 로 끝나야 함을
    강제. classifier 는 직전 AIMessage 까지 포함한 전체 대화를 평가해야 하므로,
    원본 메시지 리스트 그대로는 마지막이 AIMessage 로 끝나 거절됨. 모든 turn
    을 한 user message 안 plain text 로 직렬화해 회피.
    """
    lines: list[str] = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            lines.append(f"[user]\n{msg.content}")
        elif isinstance(msg, AIMessage):
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            tool_calls = getattr(msg, "tool_calls", None) or []
            if tool_calls:
                names = ", ".join(tc.get("name", "?") for tc in tool_calls)
                lines.append(f"[assistant]\n{content}\n(tool calls: {names})")
            else:
                lines.append(f"[assistant]\n{content}")
        elif isinstance(msg, ToolMessage):
            lines.append(f"[tool:{msg.name or '?'}]\n{msg.content}")
    return "\n\n".join(lines)


def _make_classify_response_node(llm: BaseChatModel):
    """최종 응답이 Task wrap 대상인지 LLM 추론으로 결정 (#75 PR 3).

    structured output 으로 `A2AResponseDecision` 강제 — LLM 이 자기 응답
    의도 (단순 조회 / 위임 / long-running) 를 보고 `requires_task` 채움.
    handler 는 graph state 에서 hint 만 읽어 wrap 분기.

    실패 시 (LLM 호출 / 파싱 에러) 보수적 default — `requires_task=False`
    (Message only). Task 는 LLM 이 명시한 경우만 발화.
    """
    classifier = llm.with_structured_output(A2AResponseDecision)

    async def _classify(state: State) -> dict[str, Any]:
        convo = _format_conversation_for_classifier(state["messages"])
        prompt = (
            "Below is the conversation between an A2A peer (caller) and this "
            "agent (assistant). The final [assistant] message is the response "
            "we are about to send back. Decide whether to wrap it as an A2A "
            "Task or send it as a Message.\n\n"
            "<conversation>\n"
            f"{convo}\n"
            "</conversation>"
        )
        try:
            decision = await classifier.ainvoke([
                SystemMessage(content=_CLASSIFY_PROMPT),
                HumanMessage(content=prompt),
            ])
        except Exception:
            logger.exception(
                "classify_response failed — defaulting to Message only",
            )
            return {"requires_task": False}
        if not isinstance(decision, A2AResponseDecision):
            logger.warning(
                "classify_response unexpected output type=%s — default Message only",
                type(decision).__name__,
            )
            return {"requires_task": False}
        logger.info(
            "classify_response requires_task=%s reason=%s",
            decision.requires_task, decision.reason,
        )
        return {"requires_task": decision.requires_task}

    return _classify


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
    """persona / llm / tools / (선택) checkpointer 주입해 ReAct 그래프 컴파일.

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
    builder.add_node("llm_call", _make_llm_call_node(persona, llm_with_tools))
    builder.add_node("classify_response", _make_classify_response_node(llm))
    builder.add_edge(START, "llm_call")

    if tools:
        builder.add_node("tools", _make_tool_node(tools))
        builder.add_conditional_edges(
            "llm_call",
            _should_continue,
            {"tools": "tools", "classify_response": "classify_response"},
        )
        builder.add_edge("tools", "llm_call")
    else:
        builder.add_edge("llm_call", "classify_response")

    builder.add_edge("classify_response", END)
    return builder.compile(checkpointer=checkpointer)


__all__ = ["State", "build_graph", "build_llm", "load_runtime_config"]
