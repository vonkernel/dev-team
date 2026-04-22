"""User Gateway FastAPI 서버.

두 개의 API + 정적 프론트엔드 자원을 서빙한다:

  GET  /healthz                      - liveness
  GET  /api/agent-card               - Primary AgentCard 프록시 (UI 헤더 표시용)
  POST /api/chat                     - SSE. 브라우저 → UG → Primary 중계
                                       브라우저는 `{text, contextId?}` 를 보내고
                                       SSE 스트림으로 `{type, ...}` 이벤트 수신
  GET  /                             - 정적 프론트엔드 (Vite 빌드 결과)
  GET  /assets/*                     - 프론트엔드 에셋

A2A 메시지 변환 / SSE 파싱은 UG 가 중개. 브라우저는 A2A 세부 포맷을 몰라도 됨.

환경변수:
  PRIMARY_A2A_URL    (기본: http://primary:8000/a2a/primary)
  PRIMARY_CARD_URL   (기본: http://primary:8000/.well-known/agent-card.json)
  STATIC_DIR         (기본: <모듈 디렉토리>/../../static — Dockerfile 에서 빌드된 FE 복사 위치)
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

logger = logging.getLogger(__name__)

_DEFAULT_PRIMARY_A2A_URL = "http://primary:8000/a2a/primary"
_DEFAULT_PRIMARY_CARD_URL = "http://primary:8000/.well-known/agent-card.json"

# Dockerfile 이 /app/ug/static 에 Vite 빌드 결과를 복사. 로컬 dev 에선 frontend/dist.
_MODULE_DIR = Path(__file__).resolve().parent
_DEFAULT_STATIC_DIR = _MODULE_DIR.parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.primary_a2a_url = os.environ.get(
        "PRIMARY_A2A_URL", _DEFAULT_PRIMARY_A2A_URL,
    )
    app.state.primary_card_url = os.environ.get(
        "PRIMARY_CARD_URL", _DEFAULT_PRIMARY_CARD_URL,
    )
    # 단일 httpx client 재사용 — connection pool 효율
    app.state.http = httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0))
    logger.info(
        "user-gateway ready (primary A2A: %s)", app.state.primary_a2a_url,
    )
    try:
        yield
    finally:
        await app.state.http.aclose()


app = FastAPI(
    lifespan=lifespan,
    title="User Gateway (dev-team)",
    description="Web UI + A2A 중계 for Primary agent.",
)


@app.get("/healthz")
async def healthz() -> dict[str, bool]:
    return {"ok": True}


@app.get("/api/agent-card")
async def get_agent_card(request: Request) -> JSONResponse:
    """Primary 의 AgentCard 를 그대로 프록시. 브라우저가 CORS 걱정 없이 조회."""
    http: httpx.AsyncClient = request.app.state.http
    url: str = request.app.state.primary_card_url
    try:
        r = await http.get(url)
        r.raise_for_status()
    except httpx.HTTPError as exc:
        logger.exception("failed to fetch primary AgentCard")
        raise HTTPException(
            status_code=502,
            detail=f"upstream agent-card fetch failed: {exc}",
        ) from exc
    return JSONResponse(r.json())


class ChatRequest(BaseModel):
    text: str
    context_id: str | None = None


@app.post("/api/chat")
async def chat(body: ChatRequest, request: Request) -> StreamingResponse:
    """브라우저 → UG → Primary SSE 중계.

    UG 가 브라우저에 보내는 이벤트 포맷(간단화):
        { "type": "meta",    "contextId": "..." }          # 초기 1회
        { "type": "chunk",   "text": "..." }                # LLM 토큰 조각 (N회)
        { "type": "done" }                                   # 정상 완료
        { "type": "error",   "message": "..." }             # 실패
    """
    http: httpx.AsyncClient = request.app.state.http
    primary_a2a_url: str = request.app.state.primary_a2a_url

    context_id = body.context_id or str(uuid.uuid4())
    rpc_payload = {
        "jsonrpc": "2.0",
        "id": f"ug-{uuid.uuid4()}",
        "method": "SendStreamingMessage",
        "params": {
            "message": {
                "messageId": f"ug-msg-{uuid.uuid4()}",
                "role": "ROLE_USER",
                "parts": [{"text": body.text}],
                "contextId": context_id,
            },
        },
    }

    async def event_stream():
        # 초기 meta — 프론트가 다음 요청에 contextId 이어붙일 수 있도록
        yield _sse({"type": "meta", "contextId": context_id})
        try:
            async with http.stream(
                "POST",
                primary_a2a_url,
                json=rpc_payload,
                headers={"Accept": "text/event-stream"},
                timeout=httpx.Timeout(120.0, connect=5.0),
            ) as response:
                if response.status_code != 200:
                    detail = await response.aread()
                    logger.error(
                        "primary returned %s: %s", response.status_code, detail[:500],
                    )
                    yield _sse({
                        "type": "error",
                        "message": f"primary HTTP {response.status_code}",
                    })
                    return

                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    payload_str = line[5:].strip()
                    try:
                        payload = json.loads(payload_str)
                    except json.JSONDecodeError:
                        continue

                    result = payload.get("result")
                    if not isinstance(result, dict):
                        # error envelope 등
                        err = payload.get("error")
                        if err:
                            yield _sse({
                                "type": "error",
                                "message": err.get("message", "rpc error"),
                            })
                            return
                        continue

                    kind = result.get("kind")
                    if kind == "artifact-update":
                        # text part 추출
                        text = _extract_first_text(result.get("artifact", {}))
                        if text:
                            yield _sse({"type": "chunk", "text": text})
                    elif kind == "status-update":
                        state = (result.get("status") or {}).get("state")
                        if state == "TASK_STATE_COMPLETED":
                            yield _sse({"type": "done"})
                            return
                        if state == "TASK_STATE_FAILED":
                            msg = _extract_status_message_text(result.get("status") or {})
                            yield _sse({
                                "type": "error",
                                "message": msg or "upstream failed",
                            })
                            return
                    # "task" 초기 이벤트는 UI 입장에서 무시 (meta 로 이미 알림)
        except httpx.HTTPError as exc:
            logger.exception("upstream stream failed")
            yield _sse({"type": "error", "message": f"upstream error: {exc}"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _extract_first_text(artifact: dict[str, Any]) -> str:
    parts = artifact.get("parts") or []
    for p in parts:
        t = p.get("text")
        if t:
            return t
    return ""


def _extract_status_message_text(status: dict[str, Any]) -> str:
    msg = status.get("message") or {}
    for p in msg.get("parts") or []:
        t = p.get("text")
        if t:
            return t
    return ""


# ─── 정적 프론트엔드 ──────────────────────────────────────────────────────
#  가장 마지막에 mount. `/api/*`, `/healthz` 경로보다 우선순위 낮게 두기 위해.
#  빌드된 프론트엔드 자원이 없으면 경고 로그만 남기고 API 만 서빙.
_static_dir_env = os.environ.get("STATIC_DIR")
_static_dir = Path(_static_dir_env) if _static_dir_env else _DEFAULT_STATIC_DIR
if _static_dir.is_dir() and (_static_dir / "index.html").exists():
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="frontend")
    logger.info("serving frontend from %s", _static_dir)
else:
    logger.warning(
        "frontend static dir not found at %s — API only (run `npm run build` "
        "in user-gateway/frontend for local dev)",
        _static_dir,
    )


__all__ = ["app"]
