"""HTTP 엔드포인트.

라우트 핸들러는 **어떤 자원이 필요한지** 만 선언하고 실제 I/O 는 `A2AUpstream`
등 주입된 어댑터에 위임 (DIP). 프로토콜 번역은 `translator` 순수 함수.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import anyio
import httpx
from dev_team_shared.chat_protocol import (
    SessionCreateRequest,
    SessionRead,
    SessionUpdateRequest,
)
from dev_team_shared.doc_store import DocStoreClient, SessionUpdate
from dev_team_shared.event_bus import EventBus
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from user_gateway.event_publisher import (
    publish_chat_user,
    publish_session_start,
)
from user_gateway.sse import KEEPALIVE_SENTINEL
from user_gateway.upstream import (
    A2AUpstream,
    ChatProtocolUpstream,
    UpstreamHTTPError,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/healthz")
async def healthz() -> dict[str, bool]:
    return {"ok": True}


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
    started_at = datetime.now(tz=timezone.utc)
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


@router.get("/api/agent-card")
async def get_agent_card(request: Request) -> JSONResponse:
    """Primary 의 AgentCard 를 프록시 (브라우저 CORS 회피)."""
    upstream: A2AUpstream = request.app.state.upstream
    try:
        card = await upstream.fetch_agent_card()
    except httpx.HTTPError as exc:
        logger.exception("failed to fetch primary AgentCard")
        raise HTTPException(
            status_code=502,
            detail=f"upstream agent-card fetch failed: {exc}",
        ) from exc
    return JSONResponse(card)


class ChatRequest(BaseModel):
    session_id: uuid.UUID
    text: str
    message_id: str | None = None


@router.post("/api/chat", status_code=202)
async def chat(body: ChatRequest, request: Request) -> dict[str, Any]:
    """사용자 발화 제출 (#75 PR 4 — chat protocol cutover).

    chat protocol 위로 전환됨. UG 가 즉시 202 ack 만 반환하고, 실제 응답은
    `GET /api/stream?session_id=X` 의 영속 SSE 로 흐름.

    UG 책임:
    1. `chat.append` (role=user) publish (D3)
    2. Primary 의 `POST /chat/send` 로 forward
    """
    chat_upstream: ChatProtocolUpstream = request.app.state.chat_upstream
    event_bus: EventBus | None = getattr(request.app.state, "event_bus", None)
    user_message_id = body.message_id or f"ug-msg-{uuid.uuid4()}"

    # D3: 사용자 발화는 UG 가 publish.
    await publish_chat_user(
        event_bus, str(body.session_id), body.text, user_message_id,
    )
    logger.info(
        "chat session_id=%s message_id=%s text_len=%d",
        body.session_id, user_message_id, len(body.text),
    )

    # Primary 로 forward.
    try:
        ack = await chat_upstream.chat_send(
            str(body.session_id), body.text, message_id=user_message_id,
        )
    except UpstreamHTTPError as exc:
        logger.warning("chat_send upstream %d: %s", exc.status_code, exc.detail)
        raise HTTPException(
            status_code=502, detail=f"upstream {exc.status_code}: {exc.detail[:200]}",
        ) from exc
    except httpx.HTTPError as exc:
        logger.exception("chat_send forward failed")
        raise HTTPException(status_code=502, detail=f"upstream error: {exc}") from exc

    return {
        "status": ack.get("status", "processing"),
        "message_id": user_message_id,
    }


@router.get("/api/stream")
async def stream(session_id: uuid.UUID, request: Request) -> StreamingResponse:
    """영속 SSE per session — Primary 의 `/chat/stream` 그대로 forward (#75 PR 4)."""
    chat_upstream: ChatProtocolUpstream = request.app.state.chat_upstream

    async def event_iter():
        try:
            async for line in chat_upstream.chat_stream(str(session_id)):
                if await _is_disconnected(request):
                    return
                if line is KEEPALIVE_SENTINEL:
                    yield ":keepalive\n\n"
                    continue
                assert isinstance(line, str)
                # Primary 의 SSE line 은 이미 `data: {...}\n\n` 형태 — 그대로 통과.
                yield line if line.endswith("\n\n") else f"{line}\n\n"
        except UpstreamHTTPError as exc:
            logger.warning("chat_stream upstream %d: %s", exc.status_code, exc.detail)
            yield f'data: {{"type":"error","payload":{{"message":"upstream {exc.status_code}"}}}}\n\n'
        except httpx.HTTPError:
            logger.exception("chat_stream forward failed")
            yield 'data: {"type":"error","payload":{"message":"upstream error"}}\n\n'

    return StreamingResponse(
        event_iter(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# Doc Store proxy endpoints — sessions list / history / patch
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/api/sessions", response_model=list[SessionRead])
async def list_sessions(request: Request) -> list[SessionRead]:
    """chat session 목록 (사이드바 hydrate). last_chat_at desc 정렬."""
    doc_store: DocStoreClient = request.app.state.doc_store
    # Doc Store session_list — 모든 session 반환. 시작 시각 desc 정렬.
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


@router.get("/api/history")
async def chat_history(session_id: uuid.UUID, request: Request) -> JSONResponse:
    """session 의 chats 시간순 (재연결 hydrate 용 — D14)."""
    doc_store: DocStoreClient = request.app.state.doc_store
    chats = await doc_store.chat_list_by_session(session_id)
    return JSONResponse([
        {
            "id": str(c.id),
            "session_id": str(c.session_id),
            "role": c.role,
            "sender": c.sender,
            "content": c.content,
            "message_id": c.message_id,
            "created_at": c.created_at.isoformat(),
        }
        for c in chats
    ])


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
        raise HTTPException(status_code=404, detail=f"session {session_id} not found")
    merged = {**existing.metadata, **body.metadata}
    updated = await doc_store.session_update(
        session_id, SessionUpdate(metadata=merged),
    )
    if updated is None:
        raise HTTPException(status_code=404, detail=f"session {session_id} not found")
    return SessionRead(
        id=updated.id,
        agent_endpoint=updated.agent_endpoint,
        initiator=updated.initiator,
        counterpart=updated.counterpart,
        metadata=updated.metadata,
        started_at=updated.started_at,
    )


async def _is_disconnected(request: Request) -> bool:
    try:
        return await request.is_disconnected()
    except Exception:
        return False


__all__ = ["ChatRequest", "router"]
