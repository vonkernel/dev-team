"""A2AMessageAppendProcessor — a2a.message.append → a2a_messages row.

publisher-supplied id 패턴: event.context_id / task_id / message_id 모두 UUID.
컨텍스트 / 태스크 존재 여부 확인, message_id (= a2a_messages.id) dedup.
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

        ctx = await db.a2a_context_get(event.context_id)
        if ctx is None:
            logger.warning(
                "a2a.message.append skip — context_id=%s 미존재",
                event.context_id,
            )
            return

        # task 존재 확인 (optional)
        task_id = None
        if event.task_id is not None:
            task = await db.a2a_task_get(event.task_id)
            if task is not None:
                task_id = task.id

        # message_id dedup (= a2a_messages.id)
        existing = await db.a2a_message_get(event.message_id)
        if existing is not None:
            logger.debug(
                "a2a.message.append skip — message_id=%s already exists",
                event.message_id,
            )
            return

        await db.a2a_message_create(A2AMessageCreate(
            id=event.message_id,
            a2a_context_id=ctx.id,
            a2a_task_id=task_id,
            role=event.role,
            sender=event.sender,
            parts=event.parts,
            prev_message_id=event.prev_message_id,
            metadata=event.metadata,
        ))


__all__ = ["A2AMessageAppendProcessor"]
