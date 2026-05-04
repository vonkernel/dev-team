"""SessionEndProcessor."""

from __future__ import annotations

import logging
from typing import ClassVar

from dev_team_shared.doc_store import (
    AgentSessionUpdate,
    DocStoreClient,
)
from dev_team_shared.event_bus.events import A2AEvent, SessionEndEvent

from chronicler.processors.base import EventProcessor

logger = logging.getLogger(__name__)


class SessionEndProcessor(EventProcessor):
    """세션 종료 — ended_at + reason / duration 메타 갱신."""

    event_type: ClassVar[type[A2AEvent]] = SessionEndEvent

    async def process(self, event: A2AEvent, db: DocStoreClient) -> None:
        assert isinstance(event, SessionEndEvent)
        session = await db.agent_session_find_by_context(event.context_id)
        if session is None:
            logger.warning(
                "session.end no session for context_id=%s", event.context_id,
            )
            return

        meta = dict(session.metadata)
        meta.setdefault("end_reason", event.reason)
        if event.duration_ms is not None:
            meta.setdefault("duration_ms", event.duration_ms)
        meta.update(event.metadata)

        await db.agent_session_update(
            session.id,
            AgentSessionUpdate(
                ended_at=event.timestamp,
                metadata=meta,
            ),
        )


__all__ = ["SessionEndProcessor"]
