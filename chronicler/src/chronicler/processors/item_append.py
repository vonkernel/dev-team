"""ItemAppendProcessor — #75 재설계 중 stub.

PR 2 에서 새 schema (chat / a2a layer 별) 기반으로 재작성 예정.
"""

from __future__ import annotations

import logging
from typing import ClassVar

from dev_team_shared.doc_store import DocStoreClient
from dev_team_shared.event_bus.events import A2AEvent, ItemAppendEvent

from chronicler.processors.base import EventProcessor

logger = logging.getLogger(__name__)


class ItemAppendProcessor(EventProcessor):
    """#75 PR 2 재작성 대기. 현재는 no-op."""

    event_type: ClassVar[type[A2AEvent]] = ItemAppendEvent

    async def process(self, event: A2AEvent, db: DocStoreClient) -> None:  # noqa: ARG002
        assert isinstance(event, ItemAppendEvent)
        logger.warning(
            "item.append received but processor is stubbed (#75 PR 2 will rewrite) "
            "context_id=%s role=%s sender=%s",
            event.context_id, event.role, event.sender,
        )


__all__ = ["ItemAppendProcessor"]
