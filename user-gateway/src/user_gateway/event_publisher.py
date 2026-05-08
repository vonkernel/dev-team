"""UG → Chronicler 의 chat tier 이벤트 publish 어댑터.

routes.py 는 HTTP 라우트 처리만 (SRP). 이벤트 publish 의 wire-level 디테일
(Pydantic 모델 조립 / EventBus 호출 / 실패 처리) 은 본 모듈에 격리.

publish 는 fire-and-forget — 실패해도 chat 흐름 차단 X (로그만 남김).
event_bus 가 None (Valkey 미설정) 이면 모든 helper 가 no-op.

#75 PR 2 단계 (transition): UG 가 발급한 context_id (UUID 문자열) 를 그대로
session_id 로 사용. PR 4 의 chat protocol 도입 시 server 가 session row 를
먼저 생성하고 그 id 를 UG 가 받아 사용하도록 정정 예정.
"""

from __future__ import annotations

import logging
import uuid as _uuid

from dev_team_shared.event_bus import (
    ChatAppendEvent,
    ChatSessionEndEvent,
    ChatSessionStartEvent,
    EventBus,
)

logger = logging.getLogger(__name__)

# UG 가 publish 시 사용하는 이름.
INITIATOR = "user"
COUNTERPART = "primary"   # M3: UG → Primary 가 유일. M4+ 에서 Architect 추가.


def _to_uuid(s: str) -> _uuid.UUID | None:
    """context_id 문자열이 UUID 형식이면 UUID 로 변환. 아니면 None."""
    try:
        return _uuid.UUID(s)
    except (ValueError, AttributeError):
        return None


async def publish_chat_session_start(
    bus: EventBus | None, session_id: str,
) -> None:
    """chat.session.start — UG 가 새 chat 시작 시점에 1회 publish."""
    if bus is None:
        return
    sid = _to_uuid(session_id)
    if sid is None:
        return
    try:
        await bus.publish(ChatSessionStartEvent(
            session_id=sid,
            agent_endpoint=COUNTERPART,
            initiator=INITIATOR,
            counterpart=COUNTERPART,
            metadata={"topic": "user_gateway.chat"},
        ))
    except Exception:
        logger.exception(
            "publish chat.session.start failed (session_id=%s)", session_id,
        )


async def publish_chat_user(
    bus: EventBus | None,
    session_id: str,
    text: str,
    message_id: str,
) -> None:
    """chat.append role=user — 사용자 발화 직후 publish."""
    if bus is None:
        return
    sid = _to_uuid(session_id)
    if sid is None:
        return
    try:
        await bus.publish(ChatAppendEvent(
            session_id=sid,
            role="user",
            sender="user",
            content=[{"text": text}],
            message_id=message_id,
        ))
    except Exception:
        logger.exception(
            "publish chat.append (user) failed (session_id=%s)", session_id,
        )


async def publish_chat_session_end(
    bus: EventBus | None,
    session_id: str,
    *,
    reason: str,
    duration_ms: int,
    chunks: int,
) -> None:
    """chat.session.end — chat stream 종료 시 (정상 / cancel / error 모두)."""
    if bus is None:
        return
    sid = _to_uuid(session_id)
    if sid is None:
        return
    try:
        await bus.publish(ChatSessionEndEvent(
            session_id=sid,
            reason=reason,
            metadata={"duration_ms": duration_ms, "chunks": chunks},
        ))
    except Exception:
        logger.exception(
            "publish chat.session.end failed (session_id=%s)", session_id,
        )


__all__ = [
    "COUNTERPART",
    "INITIATOR",
    "publish_chat_session_end",
    "publish_chat_session_start",
    "publish_chat_user",
]
