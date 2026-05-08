"""AssignmentCreateProcessor — assignment.create → assignments row.

publisher (P/A) 가 미리 결정한 assignment_id 를 그대로 row id 로 사용.
idempotent: 같은 id 가 이미 있으면 skip.
"""

from __future__ import annotations

import logging
from typing import ClassVar

from dev_team_shared.doc_store import AssignmentCreate, DocStoreClient
from dev_team_shared.event_bus.events import A2AEvent, AssignmentCreateEvent

from chronicler.processors.base import EventProcessor

logger = logging.getLogger(__name__)


class AssignmentCreateProcessor(EventProcessor):
    event_type: ClassVar[type[A2AEvent]] = AssignmentCreateEvent

    async def process(self, event: A2AEvent, db: DocStoreClient) -> None:
        assert isinstance(event, AssignmentCreateEvent)

        existing = await db.assignment_get(event.assignment_id)
        if existing is not None:
            logger.debug(
                "assignment.create skip — existing id=%s", event.assignment_id,
            )
            return

        await db.assignment_create(AssignmentCreate(
            id=event.assignment_id,
            title=event.title,
            description=event.description,
            status=event.status,
            owner_agent=event.owner_agent,
            root_session_id=event.root_session_id,
            issue_refs=event.issue_refs,
            metadata=event.metadata,
        ))
        logger.info(
            "assignment.create id=%s title=%s owner=%s",
            event.assignment_id, event.title, event.owner_agent,
        )


__all__ = ["AssignmentCreateProcessor"]
