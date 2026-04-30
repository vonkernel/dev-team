"""A2A Task / 이벤트 모델 조립.

각 함수는 한 종류의 모델을 만들어 반환만 한다 — 직렬화 / 송신은 envelope
모듈이 담당. 에러 텍스트 포매터(`error_detail`, `agent_timeout_text`) 도
모델 조립의 직전 단계라 본 모듈에 둔다.
"""

from __future__ import annotations

import uuid

from dev_team_shared.a2a.events import (
    Artifact,
    Task,
    TaskArtifactUpdateEvent,
    TaskStatus,
    TaskStatusUpdateEvent,
)
from dev_team_shared.a2a.types import Message, Part, Role, TaskState

from dev_team_shared.a2a.server.graph_handlers.config import AGENT_TOTAL_TIMEOUT_S
from dev_team_shared.a2a.server.graph_handlers.session import ChatContext


# ─────────────────────────────────────────────────────────────────────────────
#  에러 텍스트 (운영자 친화)
# ─────────────────────────────────────────────────────────────────────────────


def error_detail(exc: BaseException) -> str:
    """예외를 사용자·운영자 친화 문자열로. 흔한 운영 이슈 힌트 포함."""
    detail = f"{type(exc).__name__}: {exc}"
    if "credit balance" in str(exc).lower():
        detail += (
            " — Anthropic 크레딧 부족 가능성. "
            "https://console.anthropic.com/settings/billing 확인."
        )
    return detail


def agent_timeout_text() -> str:
    return f"agent total timeout after {int(AGENT_TOTAL_TIMEOUT_S)}s"


# ─────────────────────────────────────────────────────────────────────────────
#  Task / Event 팩토리
# ─────────────────────────────────────────────────────────────────────────────


def _error_message(ctx: ChatContext, text: str) -> Message:
    return Message(
        message_id=f"err-{uuid.uuid4()}",
        role=Role.AGENT,
        parts=[Part(text=text)],
        context_id=ctx.context_id,
        task_id=ctx.task_id,
    )


def make_initial_task(ctx: ChatContext, user_msg: Message) -> Task:
    return Task(
        id=ctx.task_id,
        context_id=ctx.context_id,
        status=TaskStatus(state=TaskState.SUBMITTED),
        history=[user_msg],
    )


def make_completed_task(
    ctx: ChatContext, user_msg: Message, ai_text: str,
) -> Task:
    agent_reply = Message(
        message_id=f"reply-{uuid.uuid4()}",
        role=Role.AGENT,
        parts=[Part(text=ai_text)],
        context_id=ctx.context_id,
        task_id=ctx.task_id,
    )
    return Task(
        id=ctx.task_id,
        context_id=ctx.context_id,
        status=TaskStatus(state=TaskState.COMPLETED),
        history=[user_msg, agent_reply],
    )


def make_failed_task(
    ctx: ChatContext, user_msg: Message, error_text: str,
) -> Task:
    return Task(
        id=ctx.task_id,
        context_id=ctx.context_id,
        status=TaskStatus(
            state=TaskState.FAILED,
            message=_error_message(ctx, error_text),
        ),
        history=[user_msg],
    )


def make_completed_status_event(ctx: ChatContext) -> TaskStatusUpdateEvent:
    return TaskStatusUpdateEvent(
        task_id=ctx.task_id,
        context_id=ctx.context_id,
        status=TaskStatus(state=TaskState.COMPLETED),
        final=True,
    )


def make_failed_status_event(
    ctx: ChatContext, error_text: str,
) -> TaskStatusUpdateEvent:
    return TaskStatusUpdateEvent(
        task_id=ctx.task_id,
        context_id=ctx.context_id,
        status=TaskStatus(
            state=TaskState.FAILED,
            message=_error_message(ctx, error_text),
        ),
        final=True,
    )


def make_artifact_event(
    ctx: ChatContext, text: str,
) -> TaskArtifactUpdateEvent:
    return TaskArtifactUpdateEvent(
        task_id=ctx.task_id,
        context_id=ctx.context_id,
        artifact=Artifact(
            artifact_id=ctx.artifact_id,
            parts=[Part(text=text)],
        ),
        append=True,
        last_chunk=False,
    )


__all__ = [
    "agent_timeout_text",
    "error_detail",
    "make_artifact_event",
    "make_completed_status_event",
    "make_completed_task",
    "make_failed_status_event",
    "make_failed_task",
    "make_initial_task",
]
