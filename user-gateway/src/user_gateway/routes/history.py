"""Chat history read — session 의 chats 시간순 (재연결 hydrate 용)."""

from __future__ import annotations

import logging
import uuid

from dev_team_shared.doc_store import DocStoreClient
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter()


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
            "created_at": c.created_at.isoformat(),
        }
        for c in chats
    ])


__all__ = ["router"]
