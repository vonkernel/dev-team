"""ItemAppendProcessor."""

from __future__ import annotations

import logging
from typing import ClassVar

from dev_team_shared.doc_store import (
    AgentItemCreate,
    DocStoreClient,
)
from dev_team_shared.event_bus.events import A2AEvent, ItemAppendEvent, SessionStartEvent

from chronicler.processors.base import EventProcessor
from chronicler.processors.session_start import SessionStartProcessor

logger = logging.getLogger(__name__)


class ItemAppendProcessor(EventProcessor):
    """메시지 1건 — message_id 기반 dedup. session 누락 시 자동 생성 (synthesize)."""

    event_type: ClassVar[type[A2AEvent]] = ItemAppendEvent

    async def process(self, event: A2AEvent, db: DocStoreClient) -> None:
        assert isinstance(event, ItemAppendEvent)

        session = await db.agent_session_find_by_context(event.context_id)
        if session is None:
            # session.start 누락 — 비정상이지만 데이터 보존 위해 synthesize
            logger.warning(
                "item.append no session for context_id=%s — synthesizing session.start",
                event.context_id,
            )
            await SessionStartProcessor().process(
                SessionStartEvent(
                    event_id=event.event_id + ".synth",
                    context_id=event.context_id,
                    trace_id=event.trace_id,
                    initiator=event.initiator,
                    counterpart=event.counterpart,
                    agent_task_id=event.agent_task_id,
                ),
                db,
            )
            session = await db.agent_session_find_by_context(event.context_id)

        if session is None:
            logger.error(
                "item.append synthesized session.start still failed context_id=%s",
                event.context_id,
            )
            return

        # message_id 기반 중복 검사 (best effort idempotency)
        if event.message_id:
            existing = await db.agent_item_list(
                where={
                    "agent_session_id": str(session.id),
                    "message_id": event.message_id,
                },
                limit=1,
            )
            if existing:
                logger.debug(
                    "item.append skip — duplicate message_id=%s", event.message_id,
                )
                return

        await db.agent_item_create(AgentItemCreate(
            agent_session_id=session.id,
            prev_item_id=event.prev_item_id,
            role=event.role,
            sender=event.sender,
            content=event.content,
            message_id=event.message_id,
            metadata=event.metadata,
        ))


__all__ = ["ItemAppendProcessor"]
