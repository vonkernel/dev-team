"""Event bus — 대화 이벤트 publish (chat / assignment / A2A 3 layer).

UG 가 chat lifecycle (chat.session.start / chat.append / chat.session.end) 을,
P/A 가 assignment lifecycle (assignment.create / update) 를, 각 에이전트의
A2A handler 가 a2a.* 이벤트를 publish 하면, Chronicler 가 consume 해 Doc Store
에 layer 별 영속화한다.

본 모듈은 publisher 측 (publish helper) 만 다룸. consumer 측 (XREADGROUP /
XACK) 은 chronicler/ 컨테이너 안.

추상화:
- `EventBus` ABC — 백엔드 무관 publish 계약
- `ValkeyEventBus` — Valkey Streams (XADD) 기반 구현. 기본 구현체.

이벤트 schema (#75):
- Chat layer: ChatSessionStartEvent / ChatAppendEvent / ChatSessionEndEvent
- Assignment layer: AssignmentCreateEvent / AssignmentUpdateEvent
- A2A layer: A2AContextStartEvent / A2AMessageAppendEvent / A2ATaskCreateEvent /
  A2ATaskStatusUpdateEvent / A2ATaskArtifactEvent / A2AContextEndEvent
- 공통 메타: event_id (idempotency), timestamp
"""

from dev_team_shared.event_bus.bus import EventBus, ValkeyEventBus
from dev_team_shared.event_bus.events import (
    A2AContextEndEvent,
    A2AContextStartEvent,
    A2AEvent,
    A2AMessageAppendEvent,
    A2ATaskArtifactEvent,
    A2ATaskCreateEvent,
    A2ATaskStatusUpdateEvent,
    AssignmentCreateEvent,
    AssignmentUpdateEvent,
    ChatAppendEvent,
    ChatSessionEndEvent,
    ChatSessionStartEvent,
    EventType,
)

__all__ = [
    "A2AContextEndEvent",
    "A2AContextStartEvent",
    "A2AEvent",
    "A2AMessageAppendEvent",
    "A2ATaskArtifactEvent",
    "A2ATaskCreateEvent",
    "A2ATaskStatusUpdateEvent",
    "AssignmentCreateEvent",
    "AssignmentUpdateEvent",
    "ChatAppendEvent",
    "ChatSessionEndEvent",
    "ChatSessionStartEvent",
    "EventBus",
    "EventType",
    "ValkeyEventBus",
]
