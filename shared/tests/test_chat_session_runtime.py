"""SessionRuntime / SessionRegistry / _ChatEventBuffer 단위 테스트 (#75 PR 4).

핵심 검증:
- send 가 절대 block 안 함 (graph forward progress 보장)
- buffer overflow 시 oldest message 의 chunks atomic drop
- TTL evict + 진행 task cancel
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import anyio
import pytest

from dev_team_shared.chat_protocol import (
    ChatEvent,
    ChatEventType,
    SessionRegistry,
    SessionRuntime,
)
from dev_team_shared.chat_protocol.session_runtime import _ChatEventBuffer


def _chunk(message_id: str, text: str = "x") -> ChatEvent:
    return ChatEvent(
        type=ChatEventType.CHUNK,
        payload={"message_id": message_id, "text": text},
    )


def _control(type_: ChatEventType) -> ChatEvent:
    return ChatEvent(type=type_, payload={})


class TestChatEventBuffer:
    """message-aware drop policy 단위 검증."""

    def test_send_is_non_blocking(self) -> None:
        """send 는 sync — buffer 가 가득 차도 block 안 됨."""
        buf = _ChatEventBuffer(max_messages=2)
        # max_messages=2 인데 의도적으로 3 messages 흘려도 send 가 hang 안 됨
        for i in range(50):
            buf.send(_chunk(f"m{i % 5}"))
        # 잘 작동했다면 여기 도달

    def test_oldest_message_dropped_atomically(self) -> None:
        """max_messages 초과 시 oldest message 의 모든 chunks 통째 drop."""
        buf = _ChatEventBuffer(max_messages=2)
        # m1, m2 각 3 chunks
        for _ in range(3):
            buf.send(_chunk("m1"))
        for _ in range(3):
            buf.send(_chunk("m2"))
        # 새 message m3 시작 → m1 통째 drop 되어야
        buf.send(_chunk("m3"))

        remaining_ids = [
            ev.payload["message_id"] for ev in buf._chunks
        ]
        # m1 의 chunks 0개, m2 3개, m3 1개
        assert remaining_ids.count("m1") == 0
        assert remaining_ids.count("m2") == 3
        assert remaining_ids.count("m3") == 1

    def test_same_message_id_does_not_trigger_drop(self) -> None:
        """같은 message_id 의 chunks 가 누적되어도 drop 발동 X."""
        buf = _ChatEventBuffer(max_messages=2)
        for _ in range(100):
            buf.send(_chunk("m1"))
        assert len(buf._chunks) == 100

    def test_control_events_excluded_from_backlog_count(self) -> None:
        """message_id 없는 control 이벤트 (meta/done) 는 backlog 카운트 제외."""
        buf = _ChatEventBuffer(max_messages=2)
        buf.send(_chunk("m1"))
        buf.send(_control(ChatEventType.META))
        buf.send(_control(ChatEventType.DONE))
        buf.send(_chunk("m2"))
        # backlog = {m1, m2} = 2. 한도 도달 했지만 새 메시지 X.
        # 다음 control 도 통과해야
        buf.send(_control(ChatEventType.META))
        ids = [ev.payload.get("message_id") for ev in buf._chunks]
        assert ids.count("m1") == 1
        assert ids.count("m2") == 1

    @pytest.mark.asyncio
    async def test_receive_returns_in_order(self) -> None:
        """send 한 순서 그대로 receive 가 yield."""
        buf = _ChatEventBuffer(max_messages=10)
        buf.send(_chunk("m1", "a"))
        buf.send(_chunk("m1", "b"))
        ev1 = await buf.receive()
        ev2 = await buf.receive()
        assert ev1.payload["text"] == "a"
        assert ev2.payload["text"] == "b"

    @pytest.mark.asyncio
    async def test_receive_blocks_until_send(self) -> None:
        """buffer 비었으면 receive 는 send 까지 await."""
        buf = _ChatEventBuffer(max_messages=10)

        async def producer() -> None:
            await asyncio.sleep(0.05)
            buf.send(_chunk("m1"))

        async with anyio.create_task_group() as tg:
            tg.start_soon(producer)
            ev = await buf.receive()
            assert ev is not None

    @pytest.mark.asyncio
    async def test_receive_returns_none_when_closed_and_empty(self) -> None:
        """close + 빈 버퍼 → receive None (stream 종료 신호)."""
        buf = _ChatEventBuffer(max_messages=10)
        buf.close()
        ev = await buf.receive()
        assert ev is None

    @pytest.mark.asyncio
    async def test_pending_receive_wakes_on_close(self) -> None:
        """receive 가 대기 중일 때 close 하면 None 으로 깨어남."""
        buf = _ChatEventBuffer(max_messages=10)

        async def closer() -> None:
            await asyncio.sleep(0.05)
            buf.close()

        async with anyio.create_task_group() as tg:
            tg.start_soon(closer)
            ev = await buf.receive()
            assert ev is None


class TestSessionRuntime:
    def test_send_updates_activity_at(self) -> None:
        rt = SessionRuntime(session_id=uuid4(), max_messages=5)
        before = rt.last_activity_at
        rt.send(_chunk("m1"))
        assert rt.last_activity_at >= before

    @pytest.mark.asyncio
    async def test_aclose_cancels_attached_task(self) -> None:
        rt = SessionRuntime(session_id=uuid4(), max_messages=5)
        started = asyncio.Event()
        cancelled = asyncio.Event()

        async def long_task() -> None:
            started.set()
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                cancelled.set()
                raise

        task = asyncio.create_task(long_task())
        rt.attach_task(task)
        await started.wait()
        await rt.aclose()
        assert cancelled.is_set()


class TestSessionRegistry:
    @pytest.mark.asyncio
    async def test_lazy_create_returns_same_runtime(self) -> None:
        reg = SessionRegistry(max_messages=3)
        sid = uuid4()
        rt1 = await reg.get_or_create(sid)
        rt2 = await reg.get_or_create(sid)
        assert rt1 is rt2

    @pytest.mark.asyncio
    async def test_sweeper_evicts_idle_session(self) -> None:
        """TTL 짧게 설정해 sweeper 가 idle session 을 evict."""
        reg = SessionRegistry(
            max_messages=3,
            idle_ttl_s=0.05,
            sweep_interval_s=0.02,
        )
        reg.start_sweeper()
        sid = uuid4()
        rt = await reg.get_or_create(sid)
        # idle 0.05s 초과까지 대기 + sweeper 1 iteration
        await asyncio.sleep(0.2)
        # registry 에서 사라졌어야
        rt_after = reg._sessions.get(sid)
        assert rt_after is None
        await reg.aclose()
        # buffer closed 되어 receive None
        ev = await rt.receive()
        assert ev is None

    @pytest.mark.asyncio
    async def test_aclose_closes_all_runtimes(self) -> None:
        reg = SessionRegistry(max_messages=3)
        sid1, sid2 = uuid4(), uuid4()
        rt1 = await reg.get_or_create(sid1)
        rt2 = await reg.get_or_create(sid2)
        await reg.aclose()
        assert (await rt1.receive()) is None
        assert (await rt2.receive()) is None
