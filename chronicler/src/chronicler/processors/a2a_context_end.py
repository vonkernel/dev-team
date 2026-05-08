"""A2AContextEndProcessor — a2a.context.end → a2a_contexts.ended_at + metadata."""

from __future__ import annotations

import logging
from typing import ClassVar

from dev_team_shared.doc_store import A2AContextUpdate, DocStoreClient
from dev_team_shared.event_bus.events import A2AContextEndEvent, A2AEvent

from chronicler.processors.base import EventProcessor

logger = logging.getLogger(__name__)


class A2AContextEndProcessor(EventProcessor):
    event_type: ClassVar[type[A2AEvent]] = A2AContextEndEvent

    async def process(self, event: A2AEvent, db: DocStoreClient) -> None:
        assert isinstance(event, A2AContextEndEvent)

        ctx = await db.a2a_context_find_by_context_id(event.context_id)
        if ctx is None:
            logger.warning(
                "a2a.context.end skip — wire context_id=%s 미존재",
                event.context_id,
            )
            return

        merged = {**ctx.metadata, "end_reason": event.reason, **event.metadata}
        if event.duration_ms is not None:
            merged["duration_ms"] = event.duration_ms
        await db.a2a_context_update(
            ctx.id,
            A2AContextUpdate(metadata=merged, ended_at=event.timestamp),
        )


__all__ = ["A2AContextEndProcessor"]
