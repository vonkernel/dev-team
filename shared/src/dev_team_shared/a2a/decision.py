"""A2A 응답 shape 결정 — agent graph 의 LLM 추론 산출물.

A2A 공식 가이드 *"Messages for Trivial Interactions, Tasks for Stateful
Interactions"* 따라 응답을 Message 만 / Task wrap 중 어느 형태로 보낼지
결정. 결정은 callee agent 의 graph 안 LLM 추론으로 이뤄지며 (룰베이스 X),
본 모델은 그 추론의 structured output schema.

graph 측은 `llm.with_structured_output(A2AResponseDecision)` 으로 LLM 에
schema 를 강제하고, 결정 결과를 graph state 에 저장. handler 측은 state
에서 hint 만 읽어 wrap 분기 — 분류 / 분석 로직 0.

state 누락 / 파싱 실패 시 default 는 `requires_task=False` (Message only) —
Task wrap 은 LLM 이 명시한 경우만 발화 (a2a_tasks / status_updates 등 부수
이벤트가 따라오므로).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


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


__all__ = ["A2AResponseDecision"]
