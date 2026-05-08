"""ChatSessionEndProcessor — chat.session.end → sessions.ended_at + metadata."""

from __future__ import annotations

import logging
from typing import ClassVar

from dev_team_shared.doc_store import DocStoreClient, SessionUpdate
from dev_team_shared.event_bus.events import A2AEvent, ChatSessionEndEvent

from chronicler.processors.base import EventProcessor

logger = logging.getLogger(__name__)


class ChatSessionEndProcessor(EventProcessor):
    event_type: ClassVar[type[A2AEvent]] = ChatSessionEndEvent

    async def process(self, event: A2AEvent, db: DocStoreClient) -> None:
        assert isinstance(event, ChatSessionEndEvent)

        session = await db.session_get(event.session_id)
        if session is None:
            logger.warning(
                "chat.session.end skip — session_id=%s 미존재", event.session_id,
            )
            return

        merged = {**session.metadata, "end_reason": event.reason, **event.metadata}
        await db.session_update(
            event.session_id,
            SessionUpdate(metadata=merged, ended_at=event.timestamp),
        )


__all__ = ["ChatSessionEndProcessor"]
