"""SessionEndProcessor."""

from __future__ import annotations

import logging
from typing import ClassVar

from dev_team_shared.event_bus.events import A2AEvent, SessionEndEvent
from dev_team_shared.mcp_client import StreamableMCPClient

from chronicler.processors.base import EventProcessor, call_tool

logger = logging.getLogger(__name__)


class SessionEndProcessor(EventProcessor):
    """세션 종료 — ended_at + reason / duration 메타 갱신."""

    event_type: ClassVar[type[A2AEvent]] = SessionEndEvent

    async def process(self, event: A2AEvent, mcp: StreamableMCPClient) -> None:
        assert isinstance(event, SessionEndEvent)
        session = await call_tool(
            mcp, "agent_session.find_by_context", {"context_id": event.context_id},
        )
        if session is None:
            logger.warning(
                "session.end no session for context_id=%s", event.context_id,
            )
            return

        meta = dict(session.get("metadata") or {})
        meta.setdefault("end_reason", event.reason)
        if event.duration_ms is not None:
            meta.setdefault("duration_ms", event.duration_ms)
        meta.update(event.metadata)

        await call_tool(
            mcp,
            "agent_session.update",
            {
                "id": session["id"],
                "patch": {
                    "ended_at": event.timestamp.isoformat(),
                    "metadata": meta,
                },
            },
        )


__all__ = ["SessionEndProcessor"]
