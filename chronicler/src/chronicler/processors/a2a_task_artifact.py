"""A2ATaskArtifactProcessor — a2a.task.artifact → a2a_task_artifacts row."""

from __future__ import annotations

import logging
from typing import ClassVar

from dev_team_shared.doc_store import A2ATaskArtifactCreate, DocStoreClient
from dev_team_shared.event_bus.events import A2AEvent, A2ATaskArtifactEvent

from chronicler.processors.base import EventProcessor

logger = logging.getLogger(__name__)


class A2ATaskArtifactProcessor(EventProcessor):
    event_type: ClassVar[type[A2AEvent]] = A2ATaskArtifactEvent

    async def process(self, event: A2AEvent, db: DocStoreClient) -> None:
        assert isinstance(event, A2ATaskArtifactEvent)

        task = await db.a2a_task_get(event.task_id)
        if task is None:
            logger.warning(
                "a2a.task.artifact skip — task_id=%s 미존재", event.task_id,
            )
            return

        await db.a2a_task_artifact_create(A2ATaskArtifactCreate(
            id=event.artifact_id,
            a2a_task_id=task.id,
            name=event.name,
            parts=event.parts,
            metadata=event.metadata,
        ))


__all__ = ["A2ATaskArtifactProcessor"]
