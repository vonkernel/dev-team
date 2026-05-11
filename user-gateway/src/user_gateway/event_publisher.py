"""UG → Chronicler 의 chat tier 이벤트 publish 어댑터.

routes.py 는 HTTP 라우트 처리만 (SRP). 이벤트 publish 의 wire-level 디테일
(Pydantic 모델 조립 / EventBus 호출 / 실패 처리) 은 본 모듈에 격리.

publish 는 fire-and-forget — 실패해도 chat 흐름 차단 X (로그만 남김).
event_bus 가 None (Valkey 미설정) 이면 모든 helper 가 no-op.

#75 PR 4 (chat protocol):
- session 생성은 명시적 `POST /api/sessions` 트리거 — UG 가 session_id
  (UUID) 발급 + `session.start` publish + 응답. session 은 사용자 주도
  개념이라 UG 가 발급 (D4).
- `session.start` 는 session 생성 시점 **1회만** publish (옛 "매 /api/chat
  호출마다 publish + CHR dedup" 폐기 — D4 정정).
- `session.end` 는 publish 안 함 — session 은 종료 개념 없음 (D1).
"""

from __future__ import annotations

import logging
import uuid as _uuid

from dev_team_shared.event_bus import (
    ChatAppendEvent,
    EventBus,
    SessionStartEvent,
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


async def publish_session_start(
    bus: EventBus | None,
    session_id: _uuid.UUID,
    *,
    agent_endpoint: str = COUNTERPART,
    metadata: dict | None = None,
) -> None:
    """session.start — `POST /api/sessions` 처리 시 1회만 publish.

    agent_endpoint 는 FE 가 선택한 대상 ('primary' / 'architect'). M3 엔
    'primary' 만 지원, M4+ 에 'architect' 추가.
    """
    if bus is None:
        return
    try:
        await bus.publish(SessionStartEvent(
            session_id=session_id,
            agent_endpoint=agent_endpoint,
            initiator=INITIATOR,
            counterpart=agent_endpoint,
            metadata=metadata or {"topic": "user_gateway.chat"},
        ))
    except Exception:
        logger.exception(
            "publish session.start failed (session_id=%s)", session_id,
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


__all__ = [
    "COUNTERPART",
    "INITIATOR",
    "publish_chat_user",
    "publish_session_start",
]
