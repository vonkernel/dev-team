"""ChatSessionStartProcessor — chat.session.start → sessions row.

publisher (UG) 가 발급한 session_id 를 그대로 row id 로 사용 (`SessionCreate.id`
optional 사용). 이미 존재 시 idempotent skip.
"""

from __future__ import annotations

import logging
from typing import ClassVar

from dev_team_shared.doc_store import DocStoreClient, SessionCreate
from dev_team_shared.event_bus.events import A2AEvent, ChatSessionStartEvent

from chronicler.processors.base import EventProcessor

logger = logging.getLogger(__name__)


class ChatSessionStartProcessor(EventProcessor):
    event_type: ClassVar[type[A2AEvent]] = ChatSessionStartEvent

    async def process(self, event: A2AEvent, db: DocStoreClient) -> None:
        assert isinstance(event, ChatSessionStartEvent)

        existing = await db.session_get(event.session_id)
        if existing is not None:
            logger.debug(
                "chat.session.start skip — existing session_id=%s",
                event.session_id,
            )
            return

        await db.session_create(SessionCreate(
            id=event.session_id,
            agent_endpoint=event.agent_endpoint,
            initiator=event.initiator,
            counterpart=event.counterpart,
            metadata=event.metadata,
        ))
        logger.info(
            "chat.session.start adapter ok session_id=%s endpoint=%s",
            event.session_id, event.agent_endpoint,
        )


__all__ = ["ChatSessionStartProcessor"]
