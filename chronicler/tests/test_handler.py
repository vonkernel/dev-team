"""EventHandler + Processors 단위 테스트.

DocumentDbClient 를 mock 으로 주입 — wire-level (도구명 / dict / JSON parse) 은
client 안에 격리되어 본 테스트는 typed 메서드만 검증.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from chronicler.handler import EventHandler
from chronicler.processors import ALL_PROCESSORS, EventProcessor
from chronicler.processors.session_start import SessionStartProcessor
from dev_team_shared.document_db import (
    AgentSessionRead,
    AgentTaskRead,
)
from dev_team_shared.event_bus.events import (
    ItemAppendEvent,
    SessionEndEvent,
    SessionStartEvent,
)


def _make_handler(db_mock: MagicMock) -> EventHandler:
    return EventHandler(ALL_PROCESSORS, db_mock)


def _fake_task() -> AgentTaskRead:
    now = datetime.now(tz=timezone.utc)
    return AgentTaskRead(
        id=uuid.uuid4(),
        title="t",
        description=None,
        status="open",
        owner_agent="primary",
        issue_refs=[],
        metadata={},
        created_at=now,
        updated_at=now,
    )


def _fake_session(*, context_id: str = "ctx-1") -> AgentSessionRead:
    now = datetime.now(tz=timezone.utc)
    return AgentSessionRead(
        id=uuid.uuid4(),
        agent_task_id=uuid.uuid4(),
        initiator="user",
        counterpart="primary",
        context_id=context_id,
        trace_id=None,
        topic=None,
        metadata={},
        started_at=now,
        ended_at=None,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Registry / dispatch
# ─────────────────────────────────────────────────────────────────────────────


class TestEventHandlerRegistry:
    def test_registers_all_default_processors(self) -> None:
        h = _make_handler(MagicMock())
        types = h.registered_event_types
        assert SessionStartEvent in types
        assert ItemAppendEvent in types
        assert SessionEndEvent in types

    def test_duplicate_registration_raises(self) -> None:
        class DupeProc(EventProcessor):
            event_type = SessionStartEvent
            async def process(self, event, db) -> None: ...

        with pytest.raises(ValueError, match="duplicate"):
            EventHandler(
                [SessionStartProcessor(), DupeProc()], MagicMock(),
            )

    @pytest.mark.asyncio
    async def test_unknown_event_type_skip(self) -> None:
        h = EventHandler([SessionStartProcessor()], MagicMock())
        ev = SessionEndEvent(
            context_id="c", initiator="user", counterpart="primary",
            reason="completed",
        )
        await h.handle(ev)  # 예외 없이 끝나야 함


# ─────────────────────────────────────────────────────────────────────────────
#  SessionStartProcessor
# ─────────────────────────────────────────────────────────────────────────────


class TestSessionStartProcessor:
    @pytest.mark.asyncio
    async def test_creates_fallback_task_when_missing(self) -> None:
        db = MagicMock()
        db.agent_session_find_by_context = AsyncMock(return_value=None)
        db.agent_task_create = AsyncMock(return_value=_fake_task())
        db.agent_session_create = AsyncMock(return_value=_fake_session())
        handler = _make_handler(db)

        await handler.handle(SessionStartEvent(
            context_id="ctx-1", initiator="user", counterpart="primary",
        ))

        db.agent_session_find_by_context.assert_awaited_once_with("ctx-1")
        db.agent_task_create.assert_awaited_once()
        db.agent_session_create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skip_when_session_exists(self) -> None:
        db = MagicMock()
        db.agent_session_find_by_context = AsyncMock(return_value=_fake_session())
        db.agent_task_create = AsyncMock()
        db.agent_session_create = AsyncMock()
        handler = _make_handler(db)

        await handler.handle(SessionStartEvent(
            context_id="ctx-1", initiator="user", counterpart="primary",
        ))

        db.agent_session_find_by_context.assert_awaited_once()
        db.agent_task_create.assert_not_awaited()
        db.agent_session_create.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_uses_provided_task_id(self) -> None:
        task_id = uuid.uuid4()
        db = MagicMock()
        db.agent_session_find_by_context = AsyncMock(return_value=None)
        db.agent_task_create = AsyncMock()
        db.agent_session_create = AsyncMock(return_value=_fake_session())
        handler = _make_handler(db)

        await handler.handle(SessionStartEvent(
            context_id="ctx-1",
            initiator="user", counterpart="primary",
            agent_task_id=task_id,
        ))

        db.agent_task_create.assert_not_awaited()
        # session_create 의 doc.agent_task_id 가 전달한 task_id
        session_doc = db.agent_session_create.call_args.args[0]
        assert session_doc.agent_task_id == task_id


# ─────────────────────────────────────────────────────────────────────────────
#  ItemAppendProcessor
# ─────────────────────────────────────────────────────────────────────────────


class TestItemAppendProcessor:
    @pytest.mark.asyncio
    async def test_skip_duplicate_message_id(self) -> None:
        session = _fake_session()
        # message_id dedup — list 가 1건 반환 → create 호출 안 됨
        existing_item = MagicMock()
        existing_item.message_id = "m1"

        db = MagicMock()
        db.agent_session_find_by_context = AsyncMock(return_value=session)
        db.agent_item_list = AsyncMock(return_value=[existing_item])
        db.agent_item_create = AsyncMock()
        handler = _make_handler(db)

        await handler.handle(ItemAppendEvent(
            context_id="c", initiator="user", counterpart="primary",
            role="user", sender="user",
            content={"text": "hi"}, message_id="m1",
        ))

        db.agent_item_create.assert_not_awaited()


# ─────────────────────────────────────────────────────────────────────────────
#  SessionEndProcessor
# ─────────────────────────────────────────────────────────────────────────────


class TestSessionEndProcessor:
    @pytest.mark.asyncio
    async def test_updates_ended_at(self) -> None:
        session = _fake_session()
        db = MagicMock()
        db.agent_session_find_by_context = AsyncMock(return_value=session)
        db.agent_session_update = AsyncMock(return_value=session)
        handler = _make_handler(db)

        await handler.handle(SessionEndEvent(
            context_id="c", initiator="user", counterpart="primary",
            reason="completed", duration_ms=42,
        ))

        db.agent_session_update.assert_awaited_once()
        # update 호출 인자: (session_id, AgentSessionUpdate(...))
        call_args = db.agent_session_update.call_args
        assert call_args.args[0] == session.id
        patch = call_args.args[1]
        assert patch.ended_at is not None
        assert patch.metadata["end_reason"] == "completed"
        assert patch.metadata["duration_ms"] == 42
