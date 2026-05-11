"""A2AContextStartProcessor — a2a.context.start → a2a_contexts row.

idempotent: publisher-supplied `context_id` 가 이미 row 로 있으면 skip.
"""

from __future__ import annotations

import logging
from typing import ClassVar

from dev_team_shared.doc_store import A2AContextCreate, DocStoreClient
from dev_team_shared.event_bus.events import A2AContextStartEvent, A2AEvent

from chronicler.processors.base import EventProcessor

logger = logging.getLogger(__name__)


class A2AContextStartProcessor(EventProcessor):
    event_type: ClassVar[type[A2AEvent]] = A2AContextStartEvent

    async def process(self, event: A2AEvent, db: DocStoreClient) -> None:
        assert isinstance(event, A2AContextStartEvent)

        existing = await db.a2a_context_get(event.context_id)
        if existing is not None:
            logger.debug(
                "a2a.context.start skip — context_id=%s 이미 존재",
                event.context_id,
            )
            return

        await db.a2a_context_create(A2AContextCreate(
            id=event.context_id,
            initiator_agent=event.initiator_agent,
            counterpart_agent=event.counterpart_agent,
            parent_session_id=event.parent_session_id,
            parent_assignment_id=event.parent_assignment_id,
            trace_id=event.trace_id,
            topic=event.topic,
            metadata=event.metadata,
        ))
        logger.info(
            "a2a.context.start context_id=%s initiator=%s counterpart=%s",
            event.context_id, event.initiator_agent, event.counterpart_agent,
        )


__all__ = ["A2AContextStartProcessor"]
