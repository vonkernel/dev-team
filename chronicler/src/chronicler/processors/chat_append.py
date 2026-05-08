"""ChatAppendProcessor — chat.append → chats row.

session 이 없으면 자동 생성하지 않고 warn-skip (publisher 가 chat.session.start
먼저 보내야 함). idempotent: 같은 message_id 의 chat 이 이미 있으면 skip.
"""

from __future__ import annotations

import logging
from typing import ClassVar

from dev_team_shared.doc_store import ChatCreate, DocStoreClient
from dev_team_shared.event_bus.events import A2AEvent, ChatAppendEvent

from chronicler.processors.base import EventProcessor

logger = logging.getLogger(__name__)


class ChatAppendProcessor(EventProcessor):
    event_type: ClassVar[type[A2AEvent]] = ChatAppendEvent

    async def process(self, event: A2AEvent, db: DocStoreClient) -> None:
        assert isinstance(event, ChatAppendEvent)

        # session 존재 확인 (없으면 skip)
        session = await db.session_get(event.session_id)
        if session is None:
            logger.warning(
                "chat.append skip — session_id=%s 미존재 (chat.session.start 누락)",
                event.session_id,
            )
            return

        # message_id dedup
        if event.message_id:
            existing = await db.chat_list(
                where={
                    "session_id": str(event.session_id),
                    "message_id": event.message_id,
                },
                limit=1,
            )
            if existing:
                logger.debug(
                    "chat.append skip — message_id=%s already in session=%s",
                    event.message_id, event.session_id,
                )
                return

        await db.chat_create(ChatCreate(
            session_id=event.session_id,
            prev_chat_id=event.prev_chat_id,
            role=event.role,
            sender=event.sender,
            content=event.content,
            message_id=event.message_id,
            metadata=event.metadata,
        ))


__all__ = ["ChatAppendProcessor"]
