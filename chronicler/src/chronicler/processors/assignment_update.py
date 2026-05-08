"""AssignmentUpdateProcessor — assignment.update → assignments patch."""

from __future__ import annotations

import logging
from typing import ClassVar

from dev_team_shared.doc_store import AssignmentUpdate, DocStoreClient
from dev_team_shared.event_bus.events import A2AEvent, AssignmentUpdateEvent

from chronicler.processors.base import EventProcessor

logger = logging.getLogger(__name__)


class AssignmentUpdateProcessor(EventProcessor):
    event_type: ClassVar[type[A2AEvent]] = AssignmentUpdateEvent

    async def process(self, event: A2AEvent, db: DocStoreClient) -> None:
        assert isinstance(event, AssignmentUpdateEvent)

        # 명시된 필드만 patch (Update 모델의 exclude_unset 시멘틱)
        patch = AssignmentUpdate.model_validate(
            event.model_dump(
                exclude={"event_id", "timestamp", "event_type", "assignment_id"},
                exclude_none=True,
            ),
        )
        result = await db.assignment_update(event.assignment_id, patch)
        if result is None:
            logger.warning(
                "assignment.update skip — id=%s 미존재", event.assignment_id,
            )


__all__ = ["AssignmentUpdateProcessor"]
