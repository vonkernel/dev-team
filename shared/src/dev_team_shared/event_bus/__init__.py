"""Event bus — A2A 대화 이벤트 publish.

UG / 에이전트가 자기 A2A 대화의 lifecycle 이벤트 (session.start /
item.append / session.end) 를 publish 하면, CHR (Chronicler) 가 consume
해 Document DB 에 영속화한다.

본 모듈은 publisher 측 (publish helper) 만 다룸. consumer 측 (XREADGROUP /
XACK) 은 chronicler/ 컨테이너 안에 있음.

추상화:
- `EventBus` ABC — 백엔드 무관 publish 계약
- `ValkeyEventBus` — Valkey Streams (XADD) 기반 구현. 기본 구현체.

이벤트 schema:
- `SessionStartEvent` / `ItemAppendEvent` / `SessionEndEvent` Pydantic 모델
- 공통 메타: event_id (idempotency), timestamp, trace_id, context_id
"""

from dev_team_shared.event_bus.bus import EventBus, ValkeyEventBus
from dev_team_shared.event_bus.events import (
    A2AEvent,
    EventType,
    ItemAppendEvent,
    SessionEndEvent,
    SessionStartEvent,
)

__all__ = [
    "A2AEvent",
    "EventBus",
    "EventType",
    "ItemAppendEvent",
    "SessionEndEvent",
    "SessionStartEvent",
    "ValkeyEventBus",
]
