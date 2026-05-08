"""A2AMessageAppendProcessor — a2a.message.append → a2a_messages row.

wire context_id 로 a2a_contexts 의 row UUID lookup. 없으면 warn-skip.
task_id (optional) 도 wire → row UUID lookup. message_id dedup.
"""

from __future__ import annotations

import logging
from typing import ClassVar

from dev_team_shared.doc_store import A2AMessageCreate, DocStoreClient
from dev_team_shared.event_bus.events import A2AEvent, A2AMessageAppendEvent

from chronicler.processors.base import EventProcessor

logger = logging.getLogger(__name__)


class A2AMessageAppendProcessor(EventProcessor):
    event_type: ClassVar[type[A2AEvent]] = A2AMessageAppendEvent

    async def process(self, event: A2AEvent, db: DocStoreClient) -> None:
        assert isinstance(event, A2AMessageAppendEvent)

        ctx = await db.a2a_context_find_by_context_id(event.context_id)
        if ctx is None:
            logger.warning(
                "a2a.message.append skip — wire context_id=%s 미존재",
                event.context_id,
            )
            return

        # task lookup (optional)
        task_uuid = None
        if event.task_id:
            task = await db.a2a_task_find_by_task_id(event.task_id)
            if task is not None:
                task_uuid = task.id

        # message_id dedup
        existing = await db.a2a_message_list(
            where={"a2a_context_id": str(ctx.id), "message_id": event.message_id},
            limit=1,
        )
        if existing:
            logger.debug(
                "a2a.message.append skip — message_id=%s already in context",
                event.message_id,
            )
            return

        await db.a2a_message_create(A2AMessageCreate(
            message_id=event.message_id,
            a2a_context_id=ctx.id,
            a2a_task_id=task_uuid,
            role=event.role,
            sender=event.sender,
            parts=event.parts,
            prev_message_id=event.prev_message_id,
            metadata=event.metadata,
        ))


__all__ = ["A2AMessageAppendProcessor"]
