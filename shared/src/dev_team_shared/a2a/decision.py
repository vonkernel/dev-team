"""A2A 응답 shape 결정 — agent graph 의 LLM 추론 산출물.

A2A 공식 가이드 *"Messages for Trivial Interactions, Tasks for Stateful
Interactions"* 따라 응답을 Message 만 / Task wrap 중 어느 형태로 보낼지
결정. 결정은 callee agent 의 graph 안 LLM 추론으로 이뤄지며 (룰베이스 X).

본 모듈 (모든 agent 공유 — protocol-level):

- `A2AResponseDecision` — LLM structured output schema (Pydantic)
- `DEFAULT_RESPONSE_DECISION_PROMPT` — 결정 system prompt
- `make_classify_response_node` — LangGraph 노드 factory. agent graph 가
  END 직전에 본 노드를 끼워 LLM 으로 hint 를 채움
- 사용하는 graph 의 State TypedDict 는 `requires_task: NotRequired[bool]`
  필드를 가져야 함

handler 측은 graph state 에서 hint 만 읽어 wrap 분기 — 분류 / 분석 로직 0.
state 누락 / 파싱 실패 시 default 는 `requires_task=False` (Message only) —
Task 는 LLM 이 명시한 경우만 발화.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class A2AResponseDecision(BaseModel):
    """callee agent 의 LLM 이 자기 응답이 trivial / stateful 인지 결정.

    Fields:
        requires_task: True 면 Task wrap (a2a.task.create + status transitions
            발화). False 면 Message only (a2a.message.append 만).
            기준 — caller 가 후속으로 상태 추적해야 하면 True. 단순 조회 /
            의견 / fact 확인이면 False.
        reason: LLM 의 결정 근거 (관찰 / 디버깅용. handler 는 사용 X).
    """

    requires_task: bool = Field(
        ...,
        description=(
            "Whether the response should be wrapped as an A2A Task. "
            "True if delegating work, starting long-running operations, or "
            "producing stateful outputs the caller must follow up on. "
            "False for simple queries, opinions, or fact lookups."
        ),
    )
    reason: str = Field(
        default="",
        description="Brief justification for the decision (for observability).",
    )


# A2A 프로토콜 차원의 결정 가이드 — 모든 agent 공유 default.
# agent 정체성 / 도메인 워크플로가 아닌 protocol-level 텍스트라 shared 에
# 위치. agent 별 customize 가 필요해지면 (드물 것) config 에서 override
# 가능한 형태로 확장.
DEFAULT_RESPONSE_DECISION_PROMPT = (
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


def format_conversation_for_classifier(messages: list[AnyMessage]) -> str:
    """state.messages 를 classifier LLM 이 볼 수 있는 한 덩어리 텍스트로 직렬화.

    이유: 일부 LLM provider (Anthropic) 는 대화가 user message 로 끝나야 함을
    강제. classifier 는 직전 AIMessage 까지 포함한 전체 대화를 평가해야 하므로,
    원본 messages 그대로는 마지막이 AIMessage 로 끝나 거절됨. 모든 turn 을
    한 user message 안 plain text 로 직렬화해 회피.
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


# LangGraph 노드 시그니처 — state dict 받아 부분 update dict 반환 (async).
ClassifyNode = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


def make_classify_response_node(
    llm: BaseChatModel,
    *,
    system_prompt: str = DEFAULT_RESPONSE_DECISION_PROMPT,
) -> ClassifyNode:
    """LangGraph 노드 factory — agent 응답이 Task wrap 대상인지 LLM 으로 결정.

    structured output 으로 `A2AResponseDecision` 강제 — LLM 이 자기 응답
    의도 (단순 조회 / 위임 / long-running) 를 보고 `requires_task` 채움.
    handler 는 graph state 의 `requires_task` 만 읽어 wrap 분기.

    노드는 state["messages"] 를 읽어 직렬화 → classifier LLM 호출 →
    `{"requires_task": bool}` 부분 update 반환. graph 의 State TypedDict
    는 `requires_task: NotRequired[bool]` 필드를 가져야 함.

    실패 시 (LLM 호출 / 파싱 에러) 보수적 default — `requires_task=False`
    (Message only). Task 는 LLM 이 명시한 경우만 발화.

    Args:
        llm: A2A 결정에 쓸 LLM (보통 graph 본체와 동일).
        system_prompt: override 가능. 기본은 protocol-level default.
    """
    classifier = llm.with_structured_output(A2AResponseDecision)

    async def _classify(state: dict[str, Any]) -> dict[str, Any]:
        messages = state.get("messages") or []
        convo = format_conversation_for_classifier(messages)
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
                SystemMessage(content=system_prompt),
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


__all__ = [
    "A2AResponseDecision",
    "ClassifyNode",
    "DEFAULT_RESPONSE_DECISION_PROMPT",
    "format_conversation_for_classifier",
    "make_classify_response_node",
]
