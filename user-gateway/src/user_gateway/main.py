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
자세한 설계·고려사항: `user-gateway/docs/sse.md`.

환경변수:
  PRIMARY_A2A_URL                (기본: http://primary:8000/a2a/primary)
  PRIMARY_CARD_URL               (기본: http://primary:8000/.well-known/agent-card.json)
  STATIC_DIR                     (기본: <모듈 디렉토리>/../../static — Dockerfile 에서 빌드된 FE 복사 위치)
  UG_UPSTREAM_TOTAL_TIMEOUT_S    (기본: 300) - /api/chat 전체 스트림 수명 상한
  UG_UPSTREAM_READ_TIMEOUT_S     (기본: 60)  - 개별 read timeout (httpx)
  UG_UPSTREAM_CONNECT_TIMEOUT_S  (기본: 5)   - connect timeout (httpx)
  UG_UPSTREAM_MAX_CONN           (기본: 100) - httpx pool max_connections
  UG_UPSTREAM_MAX_KEEPALIVE      (기본: 20)  - httpx pool max_keepalive_connections
  UG_UPSTREAM_CONNECT_RETRIES    (기본: 2)   - upstream 초기 connect 실패 시 재시도 횟수
  UG_SSE_KEEPALIVE_S             (기본: 15)  - SSE keepalive comment 발송 간격
  UG_SSE_DISCONNECT_POLL_S       (기본: 0.5) - client disconnect 감시 간격
  UG_ALLOWED_ORIGINS             (기본: "") - CORS allowlist (콤마 구분). 비워두면 same-origin only
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import anyio
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

# uvicorn 은 자체 logger 만 INFO 로 올려두므로 app logger 도 명시적으로 INFO.
# 세션 lifecycle 로그(sse_session.start/end/cancel 등) 가 stdout 에 흘러가도록.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

_DEFAULT_PRIMARY_A2A_URL = "http://primary:8000/a2a/primary"
_DEFAULT_PRIMARY_CARD_URL = "http://primary:8000/.well-known/agent-card.json"

# Dockerfile 이 /app/ug/static 에 Vite 빌드 결과를 복사. 로컬 dev 에선 frontend/dist.
_MODULE_DIR = Path(__file__).resolve().parent
_DEFAULT_STATIC_DIR = _MODULE_DIR.parent.parent / "static"


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning("invalid %s=%r, falling back to %s", name, raw, default)
        return default


def _env_int(name: str, default: int) -> int:
    return int(_env_float(name, float(default)))


# ─── 튜닝 상수 (환경변수 override) ────────────────────────────────────
_UPSTREAM_TOTAL_TIMEOUT_S = _env_float("UG_UPSTREAM_TOTAL_TIMEOUT_S", 300.0)
_UPSTREAM_READ_TIMEOUT_S = _env_float("UG_UPSTREAM_READ_TIMEOUT_S", 60.0)
_UPSTREAM_CONNECT_TIMEOUT_S = _env_float("UG_UPSTREAM_CONNECT_TIMEOUT_S", 5.0)
_UPSTREAM_MAX_CONN = _env_int("UG_UPSTREAM_MAX_CONN", 100)
_UPSTREAM_MAX_KEEPALIVE = _env_int("UG_UPSTREAM_MAX_KEEPALIVE", 20)
_UPSTREAM_CONNECT_RETRIES = _env_int("UG_UPSTREAM_CONNECT_RETRIES", 2)
_SSE_KEEPALIVE_S = _env_float("UG_SSE_KEEPALIVE_S", 15.0)
_SSE_DISCONNECT_POLL_S = _env_float("UG_SSE_DISCONNECT_POLL_S", 0.5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.primary_a2a_url = os.environ.get(
        "PRIMARY_A2A_URL", _DEFAULT_PRIMARY_A2A_URL,
    )
    app.state.primary_card_url = os.environ.get(
        "PRIMARY_CARD_URL", _DEFAULT_PRIMARY_CARD_URL,
    )
    # httpx.Limits 명시 — 멀티 사용자 대비 pool 크기 확보 (env override 가능)
    app.state.http = httpx.AsyncClient(
        timeout=httpx.Timeout(
            _UPSTREAM_READ_TIMEOUT_S, connect=_UPSTREAM_CONNECT_TIMEOUT_S,
        ),
        limits=httpx.Limits(
            max_connections=_UPSTREAM_MAX_CONN,
            max_keepalive_connections=_UPSTREAM_MAX_KEEPALIVE,
        ),
    )
    logger.info(
        "user-gateway ready (primary A2A: %s, total_timeout=%.0fs, "
        "keepalive=%.0fs, pool max_conn=%d)",
        app.state.primary_a2a_url,
        _UPSTREAM_TOTAL_TIMEOUT_S,
        _SSE_KEEPALIVE_S,
        _UPSTREAM_MAX_CONN,
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


# ─── Middleware: CORS (U4) ────────────────────────────────────────
_allowed_origins_raw = os.environ.get("UG_ALLOWED_ORIGINS", "").strip()
if _allowed_origins_raw:
    _allowed_origins = [o.strip() for o in _allowed_origins_raw.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    logger.info("CORS enabled for origins: %s", _allowed_origins)


# ─── Middleware: Cache-Control (U8) ───────────────────────────────
class CacheControlMiddleware(BaseHTTPMiddleware):
    """정적 자원 Cache 정책.

    - `/assets/<hash>.<ext>` → immutable (Vite 가 파일명에 hash 붙이므로 안전)
    - `/` 및 `*.html` → no-cache (index.html 내 에셋 참조는 hash 포함이라 매번 fresh fetch OK)
    - 그 외는 건드리지 않음 (API 응답 등은 각 핸들러가 결정)
    """

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        path = request.url.path
        if path.startswith("/assets/"):
            response.headers.setdefault(
                "Cache-Control", "public, max-age=31536000, immutable",
            )
        elif path == "/" or path.endswith(".html"):
            response.headers["Cache-Control"] = "no-cache"
        return response


app.add_middleware(CacheControlMiddleware)


# ─── 기본 엔드포인트 ─────────────────────────────────────────────────
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


# ─── /api/chat — SSE 중계 ────────────────────────────────────────
class ChatRequest(BaseModel):
    text: str
    context_id: str | None = None


@app.post("/api/chat")
async def chat(body: ChatRequest, request: Request) -> StreamingResponse:
    """브라우저 → UG → Primary SSE 중계.

    UG 가 브라우저에 보내는 이벤트 포맷 (sse.md §5):
        { "type": "meta",    "contextId": "..." }     # 초기 1회
        { "type": "chunk",   "text": "..." }           # LLM 토큰 조각 (N회)
        { "type": "done" }                              # 정상 완료
        { "type": "error",   "message": "..." }        # 실패

    하드닝 (sse.md §4):
    - upstream 전체 스트림 total timeout (anyio.fail_after)
    - upstream 초기 connect 실패 시 retry/backoff
    - client disconnect 주기 감시 → cascade cancel
    - SSE keepalive comment 주기 발송 (프록시 idle timeout 방어)
    - 세션 lifecycle 구조화 로깅 (start/end/cancel/error + duration/chunks)
    """
    http: httpx.AsyncClient = request.app.state.http
    primary_a2a_url: str = request.app.state.primary_a2a_url

    context_id = body.context_id or str(uuid.uuid4())
    rpc_id = f"ug-{uuid.uuid4()}"
    rpc_payload = {
        "jsonrpc": "2.0",
        "id": rpc_id,
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
        started = time.monotonic()
        chunk_count = 0
        reason = "completed"
        logger.info(
            "sse_session.start context_id=%s upstream=%s",
            context_id, primary_a2a_url,
        )

        async def _check_disconnected() -> bool:
            try:
                return await request.is_disconnected()
            except Exception:
                return False

        try:
            with anyio.fail_after(_UPSTREAM_TOTAL_TIMEOUT_S):
                # 초기 meta — FE 가 contextId 를 이어받아 thread 유지
                yield _sse({"type": "meta", "contextId": context_id})

                connect_error: Exception | None = None
                for attempt in range(_UPSTREAM_CONNECT_RETRIES + 1):
                    try:
                        async with http.stream(
                            "POST",
                            primary_a2a_url,
                            json=rpc_payload,
                            headers={"Accept": "text/event-stream"},
                        ) as response:
                            if response.status_code >= 500 and attempt < _UPSTREAM_CONNECT_RETRIES:
                                detail = (await response.aread())[:200]
                                logger.warning(
                                    "upstream %d (attempt %d/%d): %s",
                                    response.status_code,
                                    attempt + 1,
                                    _UPSTREAM_CONNECT_RETRIES + 1,
                                    detail,
                                )
                                backoff = 0.5 * (2 ** attempt)
                                await anyio.sleep(backoff)
                                continue

                            if response.status_code != 200:
                                detail = (await response.aread())[:500]
                                logger.error(
                                    "primary returned %s: %s",
                                    response.status_code, detail,
                                )
                                yield _sse({
                                    "type": "error",
                                    "message": f"primary HTTP {response.status_code}",
                                })
                                reason = "upstream_http_error"
                                return

                            # 정상 스트림 소비 — keepalive + disconnect polling 동반.
                            async for line_or_ka in _aiter_lines_with_keepalive(
                                response,
                                keepalive_s=_SSE_KEEPALIVE_S,
                            ):
                                # client disconnect 감시
                                if await _check_disconnected():
                                    logger.info(
                                        "sse_session.cancel reason=client_disconnect "
                                        "context_id=%s duration_ms=%d chunks=%d",
                                        context_id,
                                        int((time.monotonic() - started) * 1000),
                                        chunk_count,
                                    )
                                    reason = "client_disconnect"
                                    return

                                if line_or_ka is _KEEPALIVE_SENTINEL:
                                    yield ":keepalive\n\n"
                                    continue

                                line = line_or_ka
                                if not line or not line.startswith("data:"):
                                    continue
                                payload_str = line[5:].strip()
                                try:
                                    payload = json.loads(payload_str)
                                except json.JSONDecodeError:
                                    continue

                                result = payload.get("result")
                                if not isinstance(result, dict):
                                    err = payload.get("error")
                                    if err:
                                        yield _sse({
                                            "type": "error",
                                            "message": err.get("message", "rpc error"),
                                        })
                                        reason = "upstream_rpc_error"
                                        return
                                    continue

                                kind = result.get("kind")
                                if kind == "artifact-update":
                                    text = _extract_first_text(result.get("artifact", {}))
                                    if text:
                                        chunk_count += 1
                                        yield _sse({"type": "chunk", "text": text})
                                elif kind == "status-update":
                                    state = (result.get("status") or {}).get("state")
                                    if state == "TASK_STATE_COMPLETED":
                                        yield _sse({"type": "done"})
                                        return
                                    if state == "TASK_STATE_FAILED":
                                        msg = _extract_status_message_text(
                                            result.get("status") or {},
                                        )
                                        yield _sse({
                                            "type": "error",
                                            "message": msg or "upstream failed",
                                        })
                                        reason = "upstream_task_failed"
                                        return
                                # "task" 초기 이벤트는 UI 입장에서 무시 (meta 로 이미 알림)
                        # 스트림 정상 종료 — 루프 탈출
                        break
                    except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                        connect_error = exc
                        if attempt < _UPSTREAM_CONNECT_RETRIES:
                            backoff = 0.5 * (2 ** attempt)
                            logger.warning(
                                "upstream connect failed (attempt %d/%d): %s — retry in %.1fs",
                                attempt + 1,
                                _UPSTREAM_CONNECT_RETRIES + 1,
                                exc,
                                backoff,
                            )
                            await anyio.sleep(backoff)
                            continue
                        logger.exception("upstream connect failed, no retries left")
                        yield _sse({
                            "type": "error",
                            "message": f"upstream unreachable: {exc}",
                        })
                        reason = "upstream_connect_failed"
                        return
                else:
                    # for 루프가 break 없이 소진된 경우 (재시도 다 소진)
                    if connect_error is not None:
                        yield _sse({
                            "type": "error",
                            "message": f"upstream unreachable after retries: {connect_error}",
                        })
                        reason = "upstream_connect_failed"
                        return

        except TimeoutError:
            logger.warning(
                "sse_session.timeout context_id=%s after=%.1fs",
                context_id, _UPSTREAM_TOTAL_TIMEOUT_S,
            )
            yield _sse({
                "type": "error",
                "message": f"upstream timeout after {int(_UPSTREAM_TOTAL_TIMEOUT_S)}s",
            })
            reason = "total_timeout"
            return
        except httpx.HTTPError as exc:
            logger.exception("upstream stream failed")
            yield _sse({"type": "error", "message": f"upstream error: {exc}"})
            reason = "upstream_http_error"
            return
        finally:
            duration_ms = int((time.monotonic() - started) * 1000)
            logger.info(
                "sse_session.end context_id=%s reason=%s duration_ms=%d chunks=%d",
                context_id, reason, duration_ms, chunk_count,
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ─── 내부 유틸 ──────────────────────────────────────────────────────

_KEEPALIVE_SENTINEL = object()


async def _aiter_lines_with_keepalive(
    response: httpx.Response,
    *,
    keepalive_s: float,
):
    """response.aiter_lines() 를 감싸 idle 시 _KEEPALIVE_SENTINEL 을 주기 yield.

    upstream 에서 다음 line 을 기다리는 사이 `keepalive_s` 초 경과하면 sentinel 을
    내놓아 호출 측이 `:keepalive` 를 내려보낼 수 있도록 한다. 프록시 idle timeout
    방어 + disconnect polling 깨우기 용도.
    """
    iterator = response.aiter_lines()
    while True:
        try:
            with anyio.fail_after(keepalive_s):
                line = await iterator.__anext__()
        except TimeoutError:
            yield _KEEPALIVE_SENTINEL
            continue
        except StopAsyncIteration:
            return
        yield line


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
