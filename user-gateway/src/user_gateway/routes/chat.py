"""사용자 발화 제출 + 영속 SSE forward — chat protocol wire (#75 PR 4)."""

from __future__ import annotations

import logging
import uuid
from typing import Any

import httpx
from dev_team_shared.event_bus import EventBus
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from user_gateway.event_publisher import publish_chat_user
from user_gateway.sse import KEEPALIVE_SENTINEL
from user_gateway.upstream import ChatProtocolUpstream, UpstreamHTTPError

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatRequest(BaseModel):
    session_id: uuid.UUID
    text: str
    message_id: str | None = None
    prev_chat_id: uuid.UUID | None = None


@router.post("/api/chat", status_code=202)
async def chat(body: ChatRequest, request: Request) -> dict[str, Any]:
    """사용자 발화 제출 (#75 PR 4 — chat protocol cutover).

    chat protocol 위로 전환됨. UG 가 즉시 202 ack 만 반환하고, 실제 응답은
    `GET /api/stream?session_id=X` 의 영속 SSE 로 흐름.

    UG 책임:
    1. user_chat_id 발급 (publisher-supplied id, chats.id 와 1:1)
    2. `chat.append` (role=user) publish — chat_id + prev_chat_id 포함 (D3)
    3. Primary 의 `POST /chat/send` 로 forward — Primary 가 자기 응답의
       prev_chat_id 로 user_chat_id 사용
    """
    chat_upstream: ChatProtocolUpstream = request.app.state.chat_upstream
    event_bus: EventBus = request.app.state.event_bus
    user_message_id = body.message_id or f"ug-msg-{uuid.uuid4()}"
    user_chat_id = uuid.uuid4()

    # D3: 사용자 발화는 UG 가 publish.
    await publish_chat_user(
        event_bus,
        str(body.session_id),
        body.text,
        user_message_id,
        chat_id=user_chat_id,
        prev_chat_id=body.prev_chat_id,
    )
    logger.info(
        "chat session_id=%s chat_id=%s prev_chat_id=%s message_id=%s text_len=%d",
        body.session_id, user_chat_id, body.prev_chat_id,
        user_message_id, len(body.text),
    )

    # Primary 로 forward — user_chat_id 를 prev_chat_id 로 전달 (agent 응답의 직전).
    try:
        ack = await chat_upstream.chat_send(
            str(body.session_id),
            body.text,
            message_id=user_message_id,
            prev_chat_id=str(user_chat_id),
        )
    except UpstreamHTTPError as exc:
        logger.warning("chat_send upstream %d: %s", exc.status_code, exc.detail)
        raise HTTPException(
            status_code=502,
            detail=f"upstream {exc.status_code}: {exc.detail[:200]}",
        ) from exc
    except httpx.HTTPError as exc:
        logger.exception("chat_send forward failed")
        raise HTTPException(
            status_code=502, detail=f"upstream error: {exc}",
        ) from exc

    return {
        "status": ack.get("status", "processing"),
        "message_id": user_message_id,
        "chat_id": str(user_chat_id),
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
            yield (
                'data: {"type":"error","payload":'
                f'{{"message":"upstream {exc.status_code}"}}}}\n\n'
            )
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


async def _is_disconnected(request: Request) -> bool:
    try:
        return await request.is_disconnected()
    except Exception:
        return False


__all__ = ["ChatRequest", "router"]
