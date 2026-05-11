"""A2ATaskStatusUpdateProcessor — a2a.task.status_update → 2 row 효과.

1. a2a_task_status_updates row 추가 (immutable transition 로그)
2. a2a_tasks.state + completed_at (state 가 COMPLETED / FAILED 면) 갱신
"""

from __future__ import annotations

import logging
from typing import ClassVar

from dev_team_shared.doc_store import (
    A2ATaskStatusUpdateCreate,
    A2ATaskUpdate,
    DocStoreClient,
)
from dev_team_shared.event_bus.events import A2AEvent, A2ATaskStatusUpdateEvent

from chronicler.processors.base import EventProcessor

logger = logging.getLogger(__name__)

_TERMINAL_STATES = {"COMPLETED", "FAILED"}


class A2ATaskStatusUpdateProcessor(EventProcessor):
    event_type: ClassVar[type[A2AEvent]] = A2ATaskStatusUpdateEvent

    async def process(self, event: A2AEvent, db: DocStoreClient) -> None:
        assert isinstance(event, A2ATaskStatusUpdateEvent)

        task = await db.a2a_task_get(event.task_id)
        if task is None:
            logger.warning(
                "a2a.task.status_update skip — task_id=%s 미존재",
                event.task_id,
            )
            return

        # 1) immutable transition 로그
        await db.a2a_task_status_update_create(A2ATaskStatusUpdateCreate(
            a2a_task_id=task.id,
            state=event.state,
            reason=event.reason,
            metadata=event.metadata,
        ))
        # 2) a2a_tasks.state 갱신
        patch_kwargs = {"state": event.state}
        if event.state in _TERMINAL_STATES:
            patch_kwargs["completed_at"] = event.timestamp
        await db.a2a_task_update(task.id, A2ATaskUpdate(**patch_kwargs))


__all__ = ["A2ATaskStatusUpdateProcessor"]
