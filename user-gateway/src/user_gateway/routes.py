"""HTTP 엔드포인트.

라우트 핸들러는 **어떤 자원이 필요한지** 만 선언하고 실제 I/O 는 `A2AUpstream`
등 주입된 어댑터에 위임 (DIP). 프로토콜 번역은 `translator` 순수 함수.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

import anyio
import httpx
from dev_team_shared.event_bus import EventBus
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from user_gateway.event_publisher import (
    publish_chat_session_end,
    publish_chat_session_start,
    publish_chat_user,
)
from user_gateway.sse import KEEPALIVE_SENTINEL, sse_pack
from user_gateway.translator import parse_a2a_line, translate
from user_gateway.upstream import A2AUpstream, UpstreamHTTPError

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/healthz")
async def healthz() -> dict[str, bool]:
    return {"ok": True}


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
    text: str
    context_id: str | None = None


@router.post("/api/chat")
async def chat(body: ChatRequest, request: Request) -> StreamingResponse:
    """브라우저 → UG → Primary SSE 중계.

    UG → FE 이벤트 스키마 / A2A 번역 규칙: `user-gateway/docs/sse.md` §5 / §6.

    하드닝:
    - upstream 전체 total timeout (`anyio.fail_after`)
    - upstream connect retry/backoff (A2AUpstream 내부)
    - client disconnect 조기 감지 (chunk / keepalive 시점 폴링)
    - SSE keepalive comment 주기 발송 (프록시 idle timeout 방어)
    - 세션 lifecycle 구조화 로깅
    """
    upstream: A2AUpstream = request.app.state.upstream
    total_timeout_s: float = request.app.state.total_timeout_s
    event_bus: EventBus | None = getattr(request.app.state, "event_bus", None)
    context_id = body.context_id or str(uuid.uuid4())
    # 사용자 메시지 ID — UG 가 publish 하고 같은 ID 로 upstream 호출 → Primary 도 동일 ID
    # publish → CHR 의 message_id dedup 으로 중복 제거.
    user_message_id = f"ug-msg-{uuid.uuid4()}"

    async def event_stream():
        started = time.monotonic()
        chunk_count = 0
        reason = "completed"
        logger.info(
            "sse_session.start context_id=%s upstream=%s",
            context_id, upstream.a2a_url,
        )
        await publish_chat_session_start(event_bus, context_id)
        await publish_chat_user(event_bus, context_id, body.text, user_message_id)
        try:
            with anyio.fail_after(total_timeout_s):
                # 초기 meta — FE 가 contextId 를 이어받아 thread 유지
                yield sse_pack({"type": "meta", "contextId": context_id})

                async for item in upstream.stream_message(
                    body.text, context_id, message_id=user_message_id,
                ):
                    # 각 이벤트 직전 client disconnect 감시
                    if await _is_disconnected(request):
                        reason = "client_disconnect"
                        return

                    if item is KEEPALIVE_SENTINEL:
                        yield ":keepalive\n\n"
                        continue

                    # 이 시점 item 은 항상 str (upstream 계약). mypy 힌트:
                    assert isinstance(item, str)
                    payload = parse_a2a_line(item)
                    if payload is None:
                        continue
                    ug_event = translate(payload)
                    if ug_event is None:
                        continue

                    if ug_event["type"] == "chunk":
                        chunk_count += 1
                    yield sse_pack(ug_event)

                    if ug_event["type"] == "done":
                        return
                    if ug_event["type"] == "error":
                        reason = "upstream_error"
                        return

        except TimeoutError:
            yield sse_pack({
                "type": "error",
                "message": f"upstream timeout after {int(total_timeout_s)}s",
            })
            reason = "total_timeout"
        except UpstreamHTTPError as exc:
            logger.warning("upstream non-200: %s", exc)
            yield sse_pack({"type": "error", "message": str(exc)})
            reason = "upstream_http_error"
        except httpx.HTTPError as exc:
            logger.exception("upstream stream failed")
            yield sse_pack({"type": "error", "message": f"upstream error: {exc}"})
            reason = "upstream_http_error"
        finally:
            duration_ms = int((time.monotonic() - started) * 1000)
            logger.info(
                "sse_session.end context_id=%s reason=%s duration_ms=%d chunks=%d",
                context_id, reason, duration_ms, chunk_count,
            )
            await publish_chat_session_end(
                event_bus, context_id, reason=reason, duration_ms=duration_ms,
                chunks=chunk_count,
            )

    return StreamingResponse(
        event_stream(),
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
