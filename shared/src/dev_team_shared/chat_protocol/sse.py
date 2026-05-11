"""Chat protocol SSE 직렬화 helper — `ChatEvent` → `data: {json}\\n\\n`.

UG / agent 양쪽이 공유. SSE spec native (id / retry 헤더 미사용 — 단순 data
프레임만). 재연결 정책은 `GET /api/history` hydrate + 새 SSE (옵션 B, D14) —
ring buffer 없으므로 Last-Event-ID 도 사용 안 함.

keepalive 는 SSE `:comment` 라인 (`:keepalive\\n\\n`) — payload 없이 idle
proxy timeout 방어용.
"""

from __future__ import annotations

import json

from dev_team_shared.chat_protocol.schemas import ChatEvent

_KEEPALIVE_LINE = ":keepalive\n\n"


def chat_event_sse_line(event: ChatEvent) -> str:
    """`ChatEvent` → SSE `data:` 프레임. UTF-8 자연 출력 (ensure_ascii=False)."""
    payload = {"type": event.type.value, "payload": event.payload}
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"data: {body}\n\n"


def keepalive_sse_line() -> str:
    """SSE keepalive comment 라인. payload 없음."""
    return _KEEPALIVE_LINE


__all__ = ["chat_event_sse_line", "keepalive_sse_line"]
