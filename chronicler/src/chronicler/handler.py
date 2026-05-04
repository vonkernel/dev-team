"""이벤트 → Document DB MCP 호출 핸들러.

CHR 의 비즈니스 로직 한 곳. 이벤트 type 별로 어떤 MCP 도구를 부를지 결정.

Idempotency 전략 (root CLAUDE.md / chronicler/CLAUDE.md §3):
- session.start: agent_session.find_by_context 로 기존 세션 있으면 재사용 (skip create).
                 agent_task_id 미지정 시 임시 task 생성 (#34 fallback).
- item.append: agent_session 찾아 그 안에 agent_item.create. message_id 가 있으면
                중복 방지 (이미 있는 message_id 면 skip — list 후 비교).
- session.end: agent_session.update(ended_at=...).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from dev_team_shared.event_bus.events import (
    A2AEvent,
    ItemAppendEvent,
    SessionEndEvent,
    SessionStartEvent,
)
from dev_team_shared.mcp_client import StreamableMCPClient

logger = logging.getLogger(__name__)


class EventHandler:
    """A2A 이벤트 → Document DB MCP 호출.

    `mcp` 는 lifespan 에서 주입된 long-lived 클라이언트.
    """

    def __init__(self, mcp: StreamableMCPClient) -> None:
        self._mcp = mcp

    async def handle(self, event: A2AEvent) -> None:
        if isinstance(event, SessionStartEvent):
            await self._handle_session_start(event)
        elif isinstance(event, ItemAppendEvent):
            await self._handle_item_append(event)
        elif isinstance(event, SessionEndEvent):
            await self._handle_session_end(event)
        else:
            logger.warning("unknown event type: %r", event)

    # ------------------------------------------------------------------
    # session.start
    # ------------------------------------------------------------------
    async def _handle_session_start(self, event: SessionStartEvent) -> None:
        # 1) 기존 session 있으면 skip (idempotent)
        existing = await self._call_tool(
            "agent_session.find_by_context", {"context_id": event.context_id},
        )
        if existing:
            logger.debug(
                "session.start skip — existing session for context_id=%s",
                event.context_id,
            )
            return

        # 2) agent_task_id 없으면 임시 task 생성 (#34 fallback)
        agent_task_id = event.agent_task_id
        if agent_task_id is None:
            ts = event.timestamp.isoformat(timespec="seconds")
            task = await self._call_tool(
                "agent_task.create",
                {"doc": {
                    "title": f"{event.initiator} ↔ {event.counterpart} @ {ts}",
                    "owner_agent": event.counterpart,
                    "metadata": {"created_by": "chronicler-fallback"},
                }},
            )
            agent_task_id = UUID(task["id"])
            logger.info(
                "session.start fallback task created task_id=%s context_id=%s",
                agent_task_id, event.context_id,
            )

        # 3) session 생성
        await self._call_tool(
            "agent_session.create",
            {"doc": {
                "agent_task_id": str(agent_task_id),
                "initiator": event.initiator,
                "counterpart": event.counterpart,
                "context_id": event.context_id,
                "trace_id": event.trace_id,
                "topic": event.topic,
                "metadata": event.metadata,
            }},
        )

    # ------------------------------------------------------------------
    # item.append
    # ------------------------------------------------------------------
    async def _handle_item_append(self, event: ItemAppendEvent) -> None:
        session = await self._call_tool(
            "agent_session.find_by_context", {"context_id": event.context_id},
        )
        if session is None:
            # session.start 가 누락된 경우 — 비정상이지만 데이터 보존 위해 fallback
            logger.warning(
                "item.append no session for context_id=%s — synthesizing session.start",
                event.context_id,
            )
            await self._handle_session_start(SessionStartEvent(
                event_id=event.event_id + ".synth",
                context_id=event.context_id,
                trace_id=event.trace_id,
                initiator=event.initiator,
                counterpart=event.counterpart,
                agent_task_id=event.agent_task_id,
            ))
            session = await self._call_tool(
                "agent_session.find_by_context", {"context_id": event.context_id},
            )

        if session is None:
            logger.error(
                "item.append synthesized session.start still failed for context_id=%s",
                event.context_id,
            )
            return

        # message_id 기반 중복 검사 (best effort)
        if event.message_id:
            existing = await self._call_tool(
                "agent_item.list",
                {"where": {"agent_session_id": session["id"],
                            "message_id": event.message_id}},
            )
            if existing:
                logger.debug(
                    "item.append skip — duplicate message_id=%s", event.message_id,
                )
                return

        await self._call_tool(
            "agent_item.create",
            {"doc": {
                "agent_session_id": session["id"],
                "prev_item_id": str(event.prev_item_id) if event.prev_item_id else None,
                "role": event.role,
                "sender": event.sender,
                "content": event.content,
                "message_id": event.message_id,
                "metadata": event.metadata,
            }},
        )

    # ------------------------------------------------------------------
    # session.end
    # ------------------------------------------------------------------
    async def _handle_session_end(self, event: SessionEndEvent) -> None:
        session = await self._call_tool(
            "agent_session.find_by_context", {"context_id": event.context_id},
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

        await self._call_tool(
            "agent_session.update",
            {
                "id": session["id"],
                "patch": {
                    "ended_at": event.timestamp.isoformat(),
                    "metadata": meta,
                },
            },
        )

    # ------------------------------------------------------------------
    async def _call_tool(self, name: str, args: dict[str, Any]) -> Any:
        """MCP 도구 호출 + 응답 JSON parse."""
        result = await self._mcp.call_tool(name, args)
        # FastMCP 의 응답 — content[0].text 가 JSON 문자열
        if not result.content:
            return None
        import json as _json
        text = result.content[0].text
        try:
            return _json.loads(text)
        except _json.JSONDecodeError:
            # 'null' / scalar 도 JSON
            return text


__all__ = ["EventHandler"]
