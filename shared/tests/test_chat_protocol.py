"""Chat protocol wire (#75 PR 4) — schemas + SSE 직렬화 단위 테스트."""

from __future__ import annotations

import json
import uuid

import pytest
from dev_team_shared.chat_protocol import (
    ChatEvent,
    ChatEventType,
    ChatSendRequest,
    ChatSendResponse,
    SessionCreateRequest,
    SessionRead,
    SessionUpdateRequest,
    chat_event_sse_line,
    keepalive_sse_line,
)
from datetime import datetime, timezone


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


class TestSchemas:
    def test_session_create_default_endpoint_primary(self) -> None:
        req = SessionCreateRequest()
        assert req.agent_endpoint == "primary"
        assert req.metadata == {}

    def test_session_create_architect_endpoint(self) -> None:
        req = SessionCreateRequest(agent_endpoint="architect")
        assert req.agent_endpoint == "architect"

    def test_session_create_rejects_extra(self) -> None:
        with pytest.raises(Exception):  # noqa: B017
            SessionCreateRequest.model_validate(
                {"agent_endpoint": "primary", "unknown": "x"},
            )

    def test_session_read_minimal(self) -> None:
        sid = uuid.uuid4()
        ts = _now()
        rd = SessionRead(
            id=sid,
            agent_endpoint="primary",
            initiator="user",
            counterpart="primary",
            metadata={"title": "결제 모듈"},
            started_at=ts,
        )
        assert rd.id == sid
        assert rd.metadata == {"title": "결제 모듈"}

    def test_chat_send_request(self) -> None:
        sid = uuid.uuid4()
        req = ChatSendRequest(session_id=sid, text="안녕", message_id="ug-msg-1")
        assert req.session_id == sid
        assert req.text == "안녕"
        assert req.message_id == "ug-msg-1"

    def test_chat_send_response_defaults(self) -> None:
        resp = ChatSendResponse(message_id="m-1")
        assert resp.status == "processing"

    def test_session_update_request(self) -> None:
        req = SessionUpdateRequest(metadata={"title": "변경된 제목", "pinned": True})
        assert req.metadata["title"] == "변경된 제목"
        assert req.metadata["pinned"] is True


class TestSSE:
    def test_chat_event_sse_line_chunk(self) -> None:
        ev = ChatEvent(
            type=ChatEventType.CHUNK,
            payload={"text": "안녕하세요", "message_id": "m-1"},
        )
        line = chat_event_sse_line(ev)
        assert line.startswith("data: ")
        assert line.endswith("\n\n")
        body = line.removeprefix("data: ").removesuffix("\n\n")
        parsed = json.loads(body)
        assert parsed == {
            "type": "chunk",
            "payload": {"text": "안녕하세요", "message_id": "m-1"},
        }

    def test_chat_event_sse_line_done(self) -> None:
        ev = ChatEvent(type=ChatEventType.DONE)
        line = chat_event_sse_line(ev)
        parsed = json.loads(line.removeprefix("data: ").removesuffix("\n\n"))
        assert parsed == {"type": "done", "payload": {}}

    def test_chat_event_utf8_no_escape(self) -> None:
        ev = ChatEvent(type=ChatEventType.MESSAGE, payload={"text": "한글 응답"})
        line = chat_event_sse_line(ev)
        # ensure_ascii=False — 한글 원형 유지
        assert "한글 응답" in line

    def test_keepalive_line(self) -> None:
        assert keepalive_sse_line() == ":keepalive\n\n"
