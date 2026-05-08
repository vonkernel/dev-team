"""EventHandler + Processors 단위 테스트.

#75 PR 1 cut-over 후: 모든 processor 가 stub (no-op) 상태. 본 테스트는 dispatch
구조만 검증 (stub 의 실제 처리 로직은 PR 2 에서 재작성).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from dev_team_shared.event_bus.events import (
    ItemAppendEvent,
    SessionEndEvent,
    SessionStartEvent,
)

from chronicler.handler import EventHandler
from chronicler.processors import ALL_PROCESSORS, EventProcessor
from chronicler.processors.session_start import SessionStartProcessor


def _make_handler(db_mock: MagicMock) -> EventHandler:
    return EventHandler(ALL_PROCESSORS, db_mock)


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

            async def process(self, event, db) -> None: ...  # noqa: ARG002

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
        await h.handle(ev)   # 예외 없이 끝나야 함


# ─────────────────────────────────────────────────────────────────────────────
#  Stub processors (PR 2 에서 본 처리 로직 재작성)
# ─────────────────────────────────────────────────────────────────────────────


class TestProcessorStubs:
    """본 PR 의 processors 는 모두 no-op (warn-log only). DB 호출 안 함."""

    @pytest.mark.asyncio
    async def test_session_start_is_noop(self) -> None:
        from chronicler.processors.session_start import SessionStartProcessor
        db = MagicMock()
        proc = SessionStartProcessor()
        ev = SessionStartEvent(
            context_id="c", initiator="user", counterpart="primary",
        )
        await proc.process(ev, db)  # 예외 없이
        # DB call 없음 — stub 이라 어떤 메서드도 안 부름
        assert not db.method_calls

    @pytest.mark.asyncio
    async def test_item_append_is_noop(self) -> None:
        from chronicler.processors.item_append import ItemAppendProcessor
        db = MagicMock()
        proc = ItemAppendProcessor()
        ev = ItemAppendEvent(
            context_id="c", initiator="user", counterpart="primary",
            role="user", sender="user", content=[],
        )
        await proc.process(ev, db)
        assert not db.method_calls

    @pytest.mark.asyncio
    async def test_session_end_is_noop(self) -> None:
        from chronicler.processors.session_end import SessionEndProcessor
        db = MagicMock()
        proc = SessionEndProcessor()
        ev = SessionEndEvent(
            context_id="c", initiator="user", counterpart="primary",
            reason="completed",
        )
        await proc.process(ev, db)
        assert not db.method_calls
