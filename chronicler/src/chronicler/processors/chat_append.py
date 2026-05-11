"""ChatAppendProcessor — chat.append → chats row + sessions.metadata 갱신.

session 이 없으면 자동 생성하지 않고 warn-skip (publisher 가 session.start
먼저 보내야 함). idempotent: publisher-supplied `chat_id` 가 이미 있으면 skip.

#75 PR 4: chat_id 는 publisher-supplied (UG / Primary 가 발급) — chats.id 와 1:1.
wire 로 전파되어 `prev_chat_id` chain 의 결정성 보장.

#75 PR 4: sessions.metadata 자동 갱신 — D15 표준 키 중 두 개를 chronicler
가 담당.

- `title`: session 의 첫 user chat 시 content 의 text 를 truncate 해 set
  (50자 + ellipsis). 이후 user / agent chat 와 무관하게 변경 안 함 — 명시적
  rename (`PATCH /api/sessions/{id}`) 시에만 갱신.
- `last_chat_at`: 매 chat append 시 event.timestamp 로 갱신. 사이드바 정렬용.

LLM 추론 X (chronicler 는 에이전트 아님). title 의 더 정교한 요약이 필요해
지면 future PR 에서 메인 agent 가 metadata.title 을 update 하는 패턴으로 확장.
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from dev_team_shared.doc_store import ChatCreate, DocStoreClient, SessionUpdate
from dev_team_shared.event_bus.events import A2AEvent, ChatAppendEvent

from chronicler.processors.base import EventProcessor

logger = logging.getLogger(__name__)

_TITLE_MAX_LEN = 50


class ChatAppendProcessor(EventProcessor):
    event_type: ClassVar[type[A2AEvent]] = ChatAppendEvent

    async def process(self, event: A2AEvent, db: DocStoreClient) -> None:
        assert isinstance(event, ChatAppendEvent)

        # session 존재 확인 (없으면 skip)
        session = await db.session_get(event.session_id)
        if session is None:
            logger.warning(
                "chat.append skip — session_id=%s 미존재 (session.start 누락)",
                event.session_id,
            )
            return

        # chat_id dedup (publisher-supplied id 패턴)
        existing = await db.chat_get(event.chat_id)
        if existing is not None:
            logger.debug(
                "chat.append skip — chat_id=%s already in session=%s",
                event.chat_id, event.session_id,
            )
            return

        # 첫 user chat 인지 — title 자동 채움 대상 판정 (chat row 생성 직전 시점).
        is_first_user_chat = False
        if event.role == "user" and not session.metadata.get("title"):
            prior_user = await db.chat_list(
                where={"session_id": str(event.session_id), "role": "user"},
                limit=1,
            )
            is_first_user_chat = not prior_user

        await db.chat_create(ChatCreate(
            id=event.chat_id,
            session_id=event.session_id,
            prev_chat_id=event.prev_chat_id,
            role=event.role,
            sender=event.sender,
            content=event.content,
            message_id=event.message_id,
            metadata=event.metadata,
        ))

        # sessions.metadata 표준 키 자동 갱신 (D15).
        merged: dict[str, Any] = dict(session.metadata)
        merged["last_chat_at"] = event.timestamp.isoformat()
        if is_first_user_chat:
            title = _make_title(event.content)
            if title:
                merged["title"] = title
        if merged != session.metadata:
            await db.session_update(
                event.session_id, SessionUpdate(metadata=merged),
            )


def _make_title(content: list[dict[str, Any]] | dict[str, Any]) -> str:
    """첫 user chat 의 text 를 truncate 해 title 로 사용. 빈 텍스트면 빈 str."""
    text = _first_text(content).strip()
    if not text:
        return ""
    # 첫 줄만 + 길이 제한
    first_line = text.splitlines()[0].strip() if text else ""
    if len(first_line) <= _TITLE_MAX_LEN:
        return first_line
    return first_line[: _TITLE_MAX_LEN].rstrip() + "…"


def _first_text(content: list[dict[str, Any]] | dict[str, Any]) -> str:
    """A2A parts 형태 / 단일 dict 에서 첫 text 추출. 없으면 빈 str."""
    if isinstance(content, dict):
        return str(content.get("text", ""))
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and part.get("text"):
                return str(part["text"])
    return ""


__all__ = ["ChatAppendProcessor"]
