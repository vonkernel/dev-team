"""SessionStartProcessor — #75 재설계 중 stub.

PR 1 (#75) 의 cut-over 로 기존 agent_tasks / agent_sessions / agent_items 가
삭제되어 본 processor 의 적재 로직이 동작 못 함. PR 2 에서 새 schema (chat
tier: sessions / chats / assignments + a2a tier) 기반으로 재작성 예정 — 그
사이엔 no-op (이벤트 받으면 warn-log 만).
"""

from __future__ import annotations

import logging
from typing import ClassVar

from dev_team_shared.doc_store import DocStoreClient
from dev_team_shared.event_bus.events import A2AEvent, SessionStartEvent

from chronicler.processors.base import EventProcessor

logger = logging.getLogger(__name__)


class SessionStartProcessor(EventProcessor):
    """#75 PR 2 재작성 대기. 현재는 no-op."""

    event_type: ClassVar[type[A2AEvent]] = SessionStartEvent

    async def process(self, event: A2AEvent, db: DocStoreClient) -> None:  # noqa: ARG002
        assert isinstance(event, SessionStartEvent)
        logger.warning(
            "session.start received but processor is stubbed (#75 PR 2 will rewrite) "
            "context_id=%s initiator=%s counterpart=%s",
            event.context_id, event.initiator, event.counterpart,
        )


__all__ = ["SessionStartProcessor"]
