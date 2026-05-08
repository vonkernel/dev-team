"""A2ATaskCreateProcessor — a2a.task.create → a2a_tasks row.

wire context_id 로 a2a_contexts 의 row UUID lookup. wire task_id dedup.
"""

from __future__ import annotations

import logging
from typing import ClassVar

from dev_team_shared.doc_store import A2ATaskCreate, DocStoreClient
from dev_team_shared.event_bus.events import A2AEvent, A2ATaskCreateEvent

from chronicler.processors.base import EventProcessor

logger = logging.getLogger(__name__)


class A2ATaskCreateProcessor(EventProcessor):
    event_type: ClassVar[type[A2AEvent]] = A2ATaskCreateEvent

    async def process(self, event: A2AEvent, db: DocStoreClient) -> None:
        assert isinstance(event, A2ATaskCreateEvent)

        existing = await db.a2a_task_find_by_task_id(event.task_id)
        if existing is not None:
            logger.debug(
                "a2a.task.create skip — wire task_id=%s 이미 존재", event.task_id,
            )
            return

        ctx = await db.a2a_context_find_by_context_id(event.context_id)
        if ctx is None:
            logger.warning(
                "a2a.task.create skip — wire context_id=%s 미존재",
                event.context_id,
            )
            return

        await db.a2a_task_create(A2ATaskCreate(
            task_id=event.task_id,
            a2a_context_id=ctx.id,
            state=event.state,
            assignment_id=event.assignment_id,
            metadata=event.metadata,
        ))
        logger.info(
            "a2a.task.create wire_task_id=%s state=%s", event.task_id, event.state,
        )


__all__ = ["A2ATaskCreateProcessor"]
