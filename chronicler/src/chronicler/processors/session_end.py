"""SessionEndProcessor — session.end → sessions.ended_at + metadata.

#75: 한 session 은 RPC 단위가 아닌 다중 turn 을 묶는 long-lived 엔티티 →
session.end 가 두 번 이상 들어오는 게 정상 (예: TTL close 후 reopen 같은
edge case). `ended_at` 이 이미 set 이면 skip — 첫 close 시각 보존.
"""

from __future__ import annotations

import logging
from typing import ClassVar

from dev_team_shared.doc_store import DocStoreClient, SessionUpdate
from dev_team_shared.event_bus.events import A2AEvent, SessionEndEvent

from chronicler.processors.base import EventProcessor

logger = logging.getLogger(__name__)


class SessionEndProcessor(EventProcessor):
    event_type: ClassVar[type[A2AEvent]] = SessionEndEvent

    async def process(self, event: A2AEvent, db: DocStoreClient) -> None:
        assert isinstance(event, SessionEndEvent)

        session = await db.session_get(event.session_id)
        if session is None:
            logger.warning(
                "session.end skip — session_id=%s 미존재", event.session_id,
            )
            return
        if session.ended_at is not None:
            logger.debug(
                "session.end skip — session_id=%s 이미 ended_at set",
                event.session_id,
            )
            return

        merged = {**session.metadata, "end_reason": event.reason, **event.metadata}
        await db.session_update(
            event.session_id,
            SessionUpdate(metadata=merged, ended_at=event.timestamp),
        )


__all__ = ["SessionEndProcessor"]
