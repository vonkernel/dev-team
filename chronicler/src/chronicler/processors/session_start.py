"""SessionStartProcessor."""

from __future__ import annotations

import logging
from typing import ClassVar

from dev_team_shared.document_db import (
    AgentSessionCreate,
    AgentTaskCreate,
    DocumentDbClient,
)
from dev_team_shared.event_bus.events import A2AEvent, SessionStartEvent

from chronicler.processors.base import EventProcessor

logger = logging.getLogger(__name__)


class SessionStartProcessor(EventProcessor):
    """세션 시작 — find_by_context 로 idempotent. agent_task_id 미지정 시 fallback task 생성."""

    event_type: ClassVar[type[A2AEvent]] = SessionStartEvent

    async def process(self, event: A2AEvent, db: DocumentDbClient) -> None:
        assert isinstance(event, SessionStartEvent)

        # 1) 기존 session 있으면 skip (idempotent)
        existing = await db.agent_session_find_by_context(event.context_id)
        if existing is not None:
            logger.debug(
                "session.start skip — existing session for context_id=%s",
                event.context_id,
            )
            return

        # 2) agent_task_id 없으면 임시 task 생성 (#34 fallback)
        agent_task_id = event.agent_task_id
        if agent_task_id is None:
            ts = event.timestamp.isoformat(timespec="seconds")
            task = await db.agent_task_create(AgentTaskCreate(
                title=f"{event.initiator} ↔ {event.counterpart} @ {ts}",
                owner_agent=event.counterpart,
                metadata={"created_by": "chronicler-fallback"},
            ))
            agent_task_id = task.id
            logger.info(
                "session.start fallback task created task_id=%s context_id=%s",
                agent_task_id, event.context_id,
            )

        # 3) session 생성
        await db.agent_session_create(AgentSessionCreate(
            agent_task_id=agent_task_id,
            initiator=event.initiator,
            counterpart=event.counterpart,
            context_id=event.context_id,
            trace_id=event.trace_id,
            topic=event.topic,
            metadata=event.metadata,
        ))


__all__ = ["SessionStartProcessor"]
