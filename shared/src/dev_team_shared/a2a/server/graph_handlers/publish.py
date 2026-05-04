"""A2A 대화 이벤트 publish — Chronicler 가 consume.

graph_handlers 의 lifecycle (session.py / send_message.py / send_streaming.py) 에서
호출. event_bus 가 `request.app.state.event_bus` 에 없으면 no-op (publish 인프라
가 옵션이라는 의미 — 에이전트가 publish 안 해도 동작은 함).

모든 publish 는 fire-and-forget — 실패해도 본 흐름 차단 X.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import Request

from dev_team_shared.event_bus import (
    EventBus,
    ItemAppendEvent,
    SessionEndEvent,
    SessionStartEvent,
)

logger = logging.getLogger(__name__)


def _bus(request: Request) -> EventBus | None:
    """app.state.event_bus 가 있으면 반환, 없으면 None."""
    return getattr(request.app.state, "event_bus", None)


async def publish_session_start(
    request: Request,
    *,
    context_id: str,
    trace_id: str | None,
    initiator: str,
    counterpart: str,
    agent_task_id: UUID | None = None,
    topic: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    bus = _bus(request)
    if bus is None:
        return
    try:
        await bus.publish(SessionStartEvent(
            context_id=context_id,
            trace_id=trace_id,
            initiator=initiator,
            counterpart=counterpart,
            agent_task_id=agent_task_id,
            topic=topic,
            metadata=metadata or {},
        ))
    except Exception:
        logger.exception("publish_session_start failed (context_id=%s)", context_id)


async def publish_session_end(
    request: Request,
    *,
    context_id: str,
    trace_id: str | None,
    initiator: str,
    counterpart: str,
    reason: str,
    duration_ms: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    bus = _bus(request)
    if bus is None:
        return
    try:
        await bus.publish(SessionEndEvent(
            context_id=context_id,
            trace_id=trace_id,
            initiator=initiator,
            counterpart=counterpart,
            reason=reason,
            duration_ms=duration_ms,
            metadata=metadata or {},
        ))
    except Exception:
        logger.exception("publish_session_end failed (context_id=%s)", context_id)


async def publish_item_append(
    request: Request,
    *,
    context_id: str,
    trace_id: str | None,
    initiator: str,
    counterpart: str,
    role: str,
    sender: str,
    content: dict[str, Any] | list[Any],
    message_id: str | None = None,
) -> None:
    bus = _bus(request)
    if bus is None:
        return
    try:
        await bus.publish(ItemAppendEvent(
            context_id=context_id,
            trace_id=trace_id,
            initiator=initiator,
            counterpart=counterpart,
            role=role,  # type: ignore[arg-type]
            sender=sender,
            content=content,
            message_id=message_id,
        ))
    except Exception:
        logger.exception("publish_item_append failed (context_id=%s)", context_id)


__all__ = [
    "publish_item_append",
    "publish_session_end",
    "publish_session_start",
]
