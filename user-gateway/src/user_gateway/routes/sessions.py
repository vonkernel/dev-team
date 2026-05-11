"""Session lifecycle / metadata — POST / GET list / PATCH (#75 PR 4)."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from dev_team_shared.chat_protocol import (
    SessionCreateRequest,
    SessionRead,
    SessionUpdateRequest,
)
from dev_team_shared.doc_store import DocStoreClient, SessionUpdate
from dev_team_shared.event_bus import EventBus
from fastapi import APIRouter, HTTPException, Request

from user_gateway.event_publisher import publish_session_start

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/sessions", status_code=201, response_model=SessionRead)
async def create_session(
    body: SessionCreateRequest, request: Request,
) -> SessionRead:
    """새 chat session 생성 (#75 PR 4 — D4).

    UG 가 session_id (UUID) 발급 → `session.start` publish → 응답에 session_id.
    실제 `sessions` row 는 Chronicler 가 event 처리해 영속화 (eventual). FE 는
    응답의 session_id 로 즉시 `POST /api/chat` / `GET /api/stream` 진입 가능.

    chronicler 가 session row 만들기 전에 chat.append 가 도착할 수 있는 race
    는 있으나 Valkey XADD → CHR XREADGROUP 폴링 < 100ms 수준 + FE 사용자 액션
    지연이 보통 더 길어 실측 OK. 부족해지면 chronicler chat_append 에 retry
    추가 (현재는 미발견 시 warn-skip).
    """
    event_bus: EventBus | None = getattr(request.app.state, "event_bus", None)
    session_id = uuid.uuid4()
    started_at = datetime.now(tz=UTC)
    await publish_session_start(
        event_bus, session_id, agent_endpoint=body.agent_endpoint,
    )
    logger.info(
        "session_created session_id=%s agent_endpoint=%s",
        session_id, body.agent_endpoint,
    )
    return SessionRead(
        id=session_id,
        agent_endpoint=body.agent_endpoint,
        initiator="user",
        counterpart=body.agent_endpoint,
        metadata=body.metadata,
        started_at=started_at,
    )


@router.get("/api/sessions", response_model=list[SessionRead])
async def list_sessions(request: Request) -> list[SessionRead]:
    """chat session 목록 (사이드바 hydrate). last_chat_at desc 정렬."""
    doc_store: DocStoreClient = request.app.state.doc_store
    rows = await doc_store.session_list(order_by="started_at DESC", limit=100)
    return [
        SessionRead(
            id=r.id,
            agent_endpoint=r.agent_endpoint,
            initiator=r.initiator,
            counterpart=r.counterpart,
            metadata=r.metadata,
            started_at=r.started_at,
        )
        for r in rows
    ]


@router.patch("/api/sessions/{session_id}", response_model=SessionRead)
async def update_session(
    session_id: uuid.UUID,
    body: SessionUpdateRequest,
    request: Request,
) -> SessionRead:
    """session.metadata 일부 갱신 (title rename / pinned 등). merge 처리."""
    doc_store: DocStoreClient = request.app.state.doc_store
    existing = await doc_store.session_get(session_id)
    if existing is None:
        raise HTTPException(
            status_code=404, detail=f"session {session_id} not found",
        )
    merged = {**existing.metadata, **body.metadata}
    updated = await doc_store.session_update(
        session_id, SessionUpdate(metadata=merged),
    )
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"session {session_id} not found",
        )
    return SessionRead(
        id=updated.id,
        agent_endpoint=updated.agent_endpoint,
        initiator=updated.initiator,
        counterpart=updated.counterpart,
        metadata=updated.metadata,
        started_at=updated.started_at,
    )


__all__ = ["router"]
