"""A2A handler 측의 a2a.* 이벤트 publish — Chronicler 가 consume (#75).

graph_handlers (session.py / send_message.py / send_streaming.py) 에서 호출.
event_bus 가 `request.app.state.event_bus` 에 없으면 no-op.

본 모듈은 **A2A tier 의 이벤트만** publish — 에이전트 간 통신 영역.
사용자 ↔ P/A 의 chat tier 이벤트는 UG 가 자체 publish (#75 chat protocol —
PR 4 에서 도입).

#75 PR 2 까지의 transition 기간엔 UG ↔ Primary 가 여전히 A2A 위에 동작.
이 경우 UG 의 chat.* publish (UG 측) 와 Primary 의 a2a.* publish (서버 측)
가 동시에 발생 — 다른 layer 의 이벤트라 의미적 중복 아님 (PR 4 에서 UG 가
chat protocol 로 전환되면 Primary 측 a2a.* 는 inter-agent 호출 한정으로 좁아짐).

모든 publish 는 fire-and-forget — 실패해도 본 흐름 차단 X.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import Request

from dev_team_shared.event_bus import (
    A2AContextEndEvent,
    A2AContextStartEvent,
    A2AMessageAppendEvent,
    A2ATaskArtifactEvent,
    A2ATaskCreateEvent,
    A2ATaskStatusUpdateEvent,
    EventBus,
)

logger = logging.getLogger(__name__)


def _bus(request: Request) -> EventBus | None:
    """app.state.event_bus 가 있으면 반환, 없으면 None."""
    return getattr(request.app.state, "event_bus", None)


# ─────────────────────────────────────────────────────────────────────────────
#  A2A Context lifecycle
# ─────────────────────────────────────────────────────────────────────────────


async def publish_a2a_context_start(
    request: Request,
    *,
    context_id: str,
    trace_id: str | None,
    initiator_agent: str,
    counterpart_agent: str,
    parent_session_id: UUID | None = None,
    parent_assignment_id: UUID | None = None,
    topic: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    bus = _bus(request)
    if bus is None:
        return
    try:
        await bus.publish(A2AContextStartEvent(
            context_id=context_id,
            initiator_agent=initiator_agent,
            counterpart_agent=counterpart_agent,
            parent_session_id=parent_session_id,
            parent_assignment_id=parent_assignment_id,
            trace_id=trace_id,
            topic=topic,
            metadata=metadata or {},
        ))
    except Exception:
        logger.exception(
            "publish_a2a_context_start failed (context_id=%s)", context_id,
        )


async def publish_a2a_context_end(
    request: Request,
    *,
    context_id: str,
    reason: str,
    duration_ms: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    bus = _bus(request)
    if bus is None:
        return
    try:
        await bus.publish(A2AContextEndEvent(
            context_id=context_id,
            reason=reason,
            duration_ms=duration_ms,
            metadata=metadata or {},
        ))
    except Exception:
        logger.exception(
            "publish_a2a_context_end failed (context_id=%s)", context_id,
        )


# ─────────────────────────────────────────────────────────────────────────────
#  A2A Message
# ─────────────────────────────────────────────────────────────────────────────


async def publish_a2a_message_append(
    request: Request,
    *,
    context_id: str,
    message_id: str,
    role: str,
    sender: str,
    content: dict[str, Any] | list[Any],
    task_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    bus = _bus(request)
    if bus is None:
        return
    try:
        await bus.publish(A2AMessageAppendEvent(
            context_id=context_id,
            message_id=message_id,
            task_id=task_id,
            role=role,  # type: ignore[arg-type]
            sender=sender,
            parts=content,
            metadata=metadata or {},
        ))
    except Exception:
        logger.exception(
            "publish_a2a_message_append failed (context_id=%s message_id=%s)",
            context_id, message_id,
        )


# ─────────────────────────────────────────────────────────────────────────────
#  A2A Task lifecycle
# ─────────────────────────────────────────────────────────────────────────────


async def publish_a2a_task_create(
    request: Request,
    *,
    context_id: str,
    task_id: str,
    state: str = "SUBMITTED",
    assignment_id: UUID | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    bus = _bus(request)
    if bus is None:
        return
    try:
        await bus.publish(A2ATaskCreateEvent(
            context_id=context_id,
            task_id=task_id,
            state=state,  # type: ignore[arg-type]
            assignment_id=assignment_id,
            metadata=metadata or {},
        ))
    except Exception:
        logger.exception(
            "publish_a2a_task_create failed (task_id=%s)", task_id,
        )


async def publish_a2a_task_status_update(
    request: Request,
    *,
    task_id: str,
    state: str,
    reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    bus = _bus(request)
    if bus is None:
        return
    try:
        await bus.publish(A2ATaskStatusUpdateEvent(
            task_id=task_id,
            state=state,  # type: ignore[arg-type]
            reason=reason,
            metadata=metadata or {},
        ))
    except Exception:
        logger.exception(
            "publish_a2a_task_status_update failed (task_id=%s)", task_id,
        )


async def publish_a2a_task_artifact(
    request: Request,
    *,
    task_id: str,
    artifact_id: str,
    parts: dict[str, Any] | list[Any],
    name: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    bus = _bus(request)
    if bus is None:
        return
    try:
        await bus.publish(A2ATaskArtifactEvent(
            task_id=task_id,
            artifact_id=artifact_id,
            name=name,
            parts=parts,
            metadata=metadata or {},
        ))
    except Exception:
        logger.exception(
            "publish_a2a_task_artifact failed (task_id=%s artifact_id=%s)",
            task_id, artifact_id,
        )


__all__ = [
    "publish_a2a_context_end",
    "publish_a2a_context_start",
    "publish_a2a_message_append",
    "publish_a2a_task_artifact",
    "publish_a2a_task_create",
    "publish_a2a_task_status_update",
]
