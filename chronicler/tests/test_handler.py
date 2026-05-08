"""EventHandler + Processors 단위 테스트.

#75 PR 2: 11 processor (chat / assignment / a2a 3 layer) dispatch + 핵심 처리
로직 검증. DocStoreClient 는 mock — wire-level 격리는 client 안에서.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from dev_team_shared.doc_store import (
    A2AContextRead,
    A2ATaskRead,
    SessionRead,
)
from dev_team_shared.event_bus.events import (
    A2AContextEndEvent,
    A2AContextStartEvent,
    A2AMessageAppendEvent,
    A2ATaskArtifactEvent,
    A2ATaskCreateEvent,
    A2ATaskStatusUpdateEvent,
    AssignmentCreateEvent,
    AssignmentUpdateEvent,
    ChatAppendEvent,
    ChatSessionEndEvent,
    ChatSessionStartEvent,
)

from chronicler.handler import EventHandler
from chronicler.processors import (
    ALL_PROCESSORS,
    A2AContextEndProcessor,
    A2AContextStartProcessor,
    A2AMessageAppendProcessor,
    A2ATaskCreateProcessor,
    A2ATaskStatusUpdateProcessor,
    AssignmentCreateProcessor,
    ChatAppendProcessor,
    ChatSessionEndProcessor,
    ChatSessionStartProcessor,
    EventProcessor,
)


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _session_read(sid: uuid.UUID) -> SessionRead:
    return SessionRead(
        id=sid,
        agent_endpoint="primary",
        initiator="user",
        counterpart="primary",
        metadata={},
        started_at=_now(),
        ended_at=None,
    )


def _a2a_context_read(cid: uuid.UUID, wire: str = "ctx-1") -> A2AContextRead:
    return A2AContextRead(
        id=cid,
        context_id=wire,
        initiator_agent="user",
        counterpart_agent="primary",
        parent_session_id=None,
        parent_assignment_id=None,
        trace_id=None,
        topic=None,
        metadata={},
        started_at=_now(),
        ended_at=None,
    )


def _a2a_task_read(tid: uuid.UUID, wire: str = "task-1") -> A2ATaskRead:
    return A2ATaskRead(
        id=tid,
        task_id=wire,
        a2a_context_id=uuid.uuid4(),
        state="SUBMITTED",
        submitted_at=_now(),
        completed_at=None,
        assignment_id=None,
        metadata={},
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Registry / dispatch
# ─────────────────────────────────────────────────────────────────────────────


class TestEventHandlerRegistry:
    def test_registers_all_default_processors(self) -> None:
        h = EventHandler(ALL_PROCESSORS, MagicMock())
        types = h.registered_event_types
        assert ChatSessionStartEvent in types
        assert ChatAppendEvent in types
        assert ChatSessionEndEvent in types
        assert AssignmentCreateEvent in types
        assert AssignmentUpdateEvent in types
        assert A2AContextStartEvent in types
        assert A2AMessageAppendEvent in types
        assert A2ATaskCreateEvent in types
        assert A2ATaskStatusUpdateEvent in types
        assert A2ATaskArtifactEvent in types
        assert A2AContextEndEvent in types
        assert len(types) == 11

    def test_duplicate_registration_raises(self) -> None:
        class DupeProc(EventProcessor):
            event_type = ChatSessionStartEvent

            async def process(self, event, db) -> None: ...  # noqa: ARG002

        with pytest.raises(ValueError, match="duplicate"):
            EventHandler(
                [ChatSessionStartProcessor(), DupeProc()], MagicMock(),
            )


# ─────────────────────────────────────────────────────────────────────────────
#  Chat layer
# ─────────────────────────────────────────────────────────────────────────────


class TestChatSessionStartProcessor:
    @pytest.mark.asyncio
    async def test_creates_session_with_explicit_id(self) -> None:
        proc = ChatSessionStartProcessor()
        db = MagicMock()
        sid = uuid.uuid4()
        db.session_get = AsyncMock(return_value=None)
        db.session_create = AsyncMock()
        ev = ChatSessionStartEvent(
            session_id=sid, agent_endpoint="primary", counterpart="primary",
        )
        await proc.process(ev, db)
        db.session_create.assert_awaited_once()
        passed_doc = db.session_create.await_args.args[0]
        assert passed_doc.id == sid

    @pytest.mark.asyncio
    async def test_idempotent_when_exists(self) -> None:
        proc = ChatSessionStartProcessor()
        db = MagicMock()
        sid = uuid.uuid4()
        db.session_get = AsyncMock(return_value=_session_read(sid))
        db.session_create = AsyncMock()
        ev = ChatSessionStartEvent(
            session_id=sid, agent_endpoint="primary", counterpart="primary",
        )
        await proc.process(ev, db)
        db.session_create.assert_not_awaited()


class TestChatAppendProcessor:
    @pytest.mark.asyncio
    async def test_creates_chat_when_session_exists(self) -> None:
        proc = ChatAppendProcessor()
        db = MagicMock()
        sid = uuid.uuid4()
        db.session_get = AsyncMock(return_value=_session_read(sid))
        db.chat_list = AsyncMock(return_value=[])
        db.chat_create = AsyncMock()
        ev = ChatAppendEvent(
            session_id=sid, role="user", sender="user",
            content=[{"text": "hi"}], message_id="m1",
        )
        await proc.process(ev, db)
        db.chat_create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skip_when_session_missing(self) -> None:
        proc = ChatAppendProcessor()
        db = MagicMock()
        db.session_get = AsyncMock(return_value=None)
        db.chat_create = AsyncMock()
        ev = ChatAppendEvent(
            session_id=uuid.uuid4(), role="user", sender="user", content=[],
        )
        await proc.process(ev, db)
        db.chat_create.assert_not_awaited()


class TestChatSessionEndProcessor:
    @pytest.mark.asyncio
    async def test_updates_session_metadata_and_ended_at(self) -> None:
        proc = ChatSessionEndProcessor()
        db = MagicMock()
        sid = uuid.uuid4()
        db.session_get = AsyncMock(return_value=_session_read(sid))
        db.session_update = AsyncMock()
        ev = ChatSessionEndEvent(session_id=sid, reason="completed")
        await proc.process(ev, db)
        db.session_update.assert_awaited_once()


# ─────────────────────────────────────────────────────────────────────────────
#  Assignment layer
# ─────────────────────────────────────────────────────────────────────────────


class TestAssignmentCreateProcessor:
    @pytest.mark.asyncio
    async def test_creates_assignment(self) -> None:
        proc = AssignmentCreateProcessor()
        db = MagicMock()
        aid = uuid.uuid4()
        db.assignment_get = AsyncMock(return_value=None)
        db.assignment_create = AsyncMock()
        ev = AssignmentCreateEvent(
            assignment_id=aid, title="결제 모듈", owner_agent="primary",
        )
        await proc.process(ev, db)
        db.assignment_create.assert_awaited_once()
        passed_doc = db.assignment_create.await_args.args[0]
        assert passed_doc.id == aid


# ─────────────────────────────────────────────────────────────────────────────
#  A2A layer
# ─────────────────────────────────────────────────────────────────────────────


class TestA2AContextStartProcessor:
    @pytest.mark.asyncio
    async def test_creates_a2a_context(self) -> None:
        proc = A2AContextStartProcessor()
        db = MagicMock()
        db.a2a_context_find_by_context_id = AsyncMock(return_value=None)
        db.a2a_context_create = AsyncMock()
        ev = A2AContextStartEvent(
            context_id="ctx-1",
            initiator_agent="primary",
            counterpart_agent="engineer",
        )
        await proc.process(ev, db)
        db.a2a_context_create.assert_awaited_once()


class TestA2AMessageAppendProcessor:
    @pytest.mark.asyncio
    async def test_resolves_context_and_creates_message(self) -> None:
        proc = A2AMessageAppendProcessor()
        db = MagicMock()
        cid = uuid.uuid4()
        db.a2a_context_find_by_context_id = AsyncMock(
            return_value=_a2a_context_read(cid),
        )
        db.a2a_message_list = AsyncMock(return_value=[])
        db.a2a_message_create = AsyncMock()
        ev = A2AMessageAppendEvent(
            context_id="ctx-1", message_id="m1",
            role="user", sender="primary", parts=[{"text": "hi"}],
        )
        await proc.process(ev, db)
        db.a2a_message_create.assert_awaited_once()


class TestA2ATaskCreateProcessor:
    @pytest.mark.asyncio
    async def test_resolves_context_and_creates_task(self) -> None:
        proc = A2ATaskCreateProcessor()
        db = MagicMock()
        cid = uuid.uuid4()
        db.a2a_task_find_by_task_id = AsyncMock(return_value=None)
        db.a2a_context_find_by_context_id = AsyncMock(
            return_value=_a2a_context_read(cid),
        )
        db.a2a_task_create = AsyncMock()
        ev = A2ATaskCreateEvent(
            context_id="ctx-1", task_id="task-1", state="SUBMITTED",
        )
        await proc.process(ev, db)
        db.a2a_task_create.assert_awaited_once()


class TestA2ATaskStatusUpdateProcessor:
    @pytest.mark.asyncio
    async def test_inserts_log_and_updates_task_state(self) -> None:
        proc = A2ATaskStatusUpdateProcessor()
        db = MagicMock()
        tid = uuid.uuid4()
        db.a2a_task_find_by_task_id = AsyncMock(return_value=_a2a_task_read(tid))
        db.a2a_task_status_update_create = AsyncMock()
        db.a2a_task_update = AsyncMock()
        ev = A2ATaskStatusUpdateEvent(task_id="task-1", state="WORKING")
        await proc.process(ev, db)
        db.a2a_task_status_update_create.assert_awaited_once()
        db.a2a_task_update.assert_awaited_once()


class TestA2AContextEndProcessor:
    @pytest.mark.asyncio
    async def test_updates_context_metadata_and_ended_at(self) -> None:
        proc = A2AContextEndProcessor()
        db = MagicMock()
        cid = uuid.uuid4()
        db.a2a_context_find_by_context_id = AsyncMock(
            return_value=_a2a_context_read(cid),
        )
        db.a2a_context_update = AsyncMock()
        ev = A2AContextEndEvent(
            context_id="ctx-1", reason="completed", duration_ms=1234,
        )
        await proc.process(ev, db)
        db.a2a_context_update.assert_awaited_once()
