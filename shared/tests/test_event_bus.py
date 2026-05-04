"""ValkeyEventBus 단위 테스트 — fakeredis 또는 진짜 Valkey 사용.

진짜 Valkey 가 떠 있으면 사용 (compose `mcp` profile up). 없으면 skip.
"""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
import redis.asyncio as redis

from dev_team_shared.event_bus import (
    ItemAppendEvent,
    SessionEndEvent,
    SessionStartEvent,
    ValkeyEventBus,
)
from dev_team_shared.event_bus.bus import A2A_EVENTS_STREAM

_VALKEY_URL = os.environ.get("EVENT_BUS_TEST_URL", "redis://localhost:6379")


@pytest_asyncio.fixture
async def stream_name() -> str:
    """테스트마다 별 stream name 사용 (격리)."""
    return f"a2a-events-test-{uuid.uuid4().hex[:8]}"


@pytest_asyncio.fixture
async def bus_and_client(stream_name, monkeypatch):  # type: ignore[no-untyped-def]
    """test-only stream name 으로 ValkeyEventBus + 검증용 raw client."""
    # bus 가 사용하는 stream 이름을 monkeypatch 로 임시 교체
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
    async def test_publish_session_start(self, bus_and_client) -> None:
        bus, raw, stream = bus_and_client
        await bus.publish(SessionStartEvent(
            context_id="ctx-1",
            initiator="user",
            counterpart="primary",
            trace_id="trace-1",
        ))
        # XLEN 으로 확인
        length = await raw.xlen(stream)
        assert length == 1

    @pytest.mark.asyncio
    async def test_publish_3_event_types(self, bus_and_client) -> None:
        bus, raw, stream = bus_and_client
        await bus.publish(SessionStartEvent(
            context_id="c", initiator="user", counterpart="primary",
        ))
        await bus.publish(ItemAppendEvent(
            context_id="c", initiator="user", counterpart="primary",
            role="user", sender="user", content={"text": "hi"},
        ))
        await bus.publish(SessionEndEvent(
            context_id="c", initiator="user", counterpart="primary",
            reason="completed", duration_ms=100,
        ))
        assert await raw.xlen(stream) == 3
        # event_type 필드 정확
        entries = await raw.xrange(stream)
        types = [fields[b"event_type"] for _id, fields in entries]
        assert types == [b"session.start", b"item.append", b"session.end"]
