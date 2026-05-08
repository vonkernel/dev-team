"""ValkeyEventBus 단위 테스트 — 진짜 Valkey 가 떠 있으면 사용, 없으면 skip.

#75 PR 2: 11 events (chat / assignment / a2a 3 layer) wire-level publish 검증.
"""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
import redis.asyncio as redis

from dev_team_shared.event_bus import (
    A2AContextEndEvent,
    A2AContextStartEvent,
    A2AMessageAppendEvent,
    A2ATaskCreateEvent,
    A2ATaskStatusUpdateEvent,
    AssignmentCreateEvent,
    ChatAppendEvent,
    ChatSessionEndEvent,
    ChatSessionStartEvent,
    ValkeyEventBus,
)
from dev_team_shared.event_bus.bus import A2A_EVENTS_STREAM

_VALKEY_URL = os.environ.get("EVENT_BUS_TEST_URL", "redis://localhost:6379")


@pytest_asyncio.fixture
async def stream_name() -> str:
    return f"a2a-events-test-{uuid.uuid4().hex[:8]}"


@pytest_asyncio.fixture
async def bus_and_client(stream_name, monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        "dev_team_shared.event_bus.bus.A2A_EVENTS_STREAM",
        stream_name,
    )

    try:
        bus = await ValkeyEventBus.create(_VALKEY_URL)
    except Exception:
        pytest.skip(f"Valkey at {_VALKEY_URL} unavailable")

    raw = redis.from_url(_VALKEY_URL, decode_responses=False)
    try:
        await raw.delete(stream_name)
        yield bus, raw, stream_name
    finally:
        await raw.delete(stream_name)
        await bus.aclose()
        await raw.aclose()


class TestValkeyEventBus:
    @pytest.mark.asyncio
    async def test_publish_chat_session_start(self, bus_and_client) -> None:
        bus, raw, stream = bus_and_client
        await bus.publish(ChatSessionStartEvent(
            session_id=uuid.uuid4(),
            agent_endpoint="primary",
            counterpart="primary",
        ))
        assert await raw.xlen(stream) == 1

    @pytest.mark.asyncio
    async def test_publish_chat_layer(self, bus_and_client) -> None:
        bus, raw, stream = bus_and_client
        sid = uuid.uuid4()
        await bus.publish(ChatSessionStartEvent(
            session_id=sid, agent_endpoint="primary", counterpart="primary",
        ))
        await bus.publish(ChatAppendEvent(
            session_id=sid, role="user", sender="user",
            content=[{"text": "hi"}], message_id="m-1",
        ))
        await bus.publish(ChatSessionEndEvent(
            session_id=sid, reason="completed",
        ))
        assert await raw.xlen(stream) == 3
        entries = await raw.xrange(stream)
        types = [fields[b"event_type"] for _id, fields in entries]
        assert types == [b"chat.session.start", b"chat.append", b"chat.session.end"]

    @pytest.mark.asyncio
    async def test_publish_a2a_layer(self, bus_and_client) -> None:
        bus, raw, stream = bus_and_client
        await bus.publish(A2AContextStartEvent(
            context_id="ctx-1",
            initiator_agent="primary",
            counterpart_agent="engineer",
        ))
        await bus.publish(A2ATaskCreateEvent(
            context_id="ctx-1", task_id="task-1", state="SUBMITTED",
        ))
        await bus.publish(A2AMessageAppendEvent(
            context_id="ctx-1", message_id="m-1", task_id="task-1",
            role="user", sender="primary", parts=[{"text": "do it"}],
        ))
        await bus.publish(A2ATaskStatusUpdateEvent(
            task_id="task-1", state="WORKING",
        ))
        await bus.publish(A2AContextEndEvent(
            context_id="ctx-1", reason="completed", duration_ms=42,
        ))
        assert await raw.xlen(stream) == 5
        entries = await raw.xrange(stream)
        types = [fields[b"event_type"] for _id, fields in entries]
        assert types == [
            b"a2a.context.start",
            b"a2a.task.create",
            b"a2a.message.append",
            b"a2a.task.status_update",
            b"a2a.context.end",
        ]

    @pytest.mark.asyncio
    async def test_publish_assignment_event(self, bus_and_client) -> None:
        bus, raw, stream = bus_and_client
        await bus.publish(AssignmentCreateEvent(
            assignment_id=uuid.uuid4(),
            title="결제 모듈 설계",
            owner_agent="primary",
        ))
        assert await raw.xlen(stream) == 1
        entries = await raw.xrange(stream)
        assert entries[0][1][b"event_type"] == b"assignment.create"
