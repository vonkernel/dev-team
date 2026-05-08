"""SessionEndProcessor — #75 재설계 중 stub.

PR 2 에서 새 schema (chat / a2a layer 별) 기반으로 재작성 예정.
"""

from __future__ import annotations

import logging
from typing import ClassVar

from dev_team_shared.doc_store import DocStoreClient
from dev_team_shared.event_bus.events import A2AEvent, SessionEndEvent

from chronicler.processors.base import EventProcessor

logger = logging.getLogger(__name__)


class SessionEndProcessor(EventProcessor):
    """#75 PR 2 재작성 대기. 현재는 no-op."""

    event_type: ClassVar[type[A2AEvent]] = SessionEndEvent

    async def process(self, event: A2AEvent, db: DocStoreClient) -> None:  # noqa: ARG002
        assert isinstance(event, SessionEndEvent)
        logger.warning(
            "session.end received but processor is stubbed (#75 PR 2 will rewrite) "
            "context_id=%s reason=%s duration_ms=%s",
            event.context_id, event.reason, event.duration_ms,
        )


__all__ = ["SessionEndProcessor"]
