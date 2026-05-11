"""User Gateway FastAPI 서버 — 조립 레이어.

각 관심사는 별도 모듈에 분리되어 있고 (SRP), 본 파일은 다음만 담당:

1. 설정 로드 (`config.load_config_from_env`)
2. 미들웨어 등록 (`CORSMiddleware`, `CacheControlMiddleware`)
3. 의존성 주입 (`lifespan` 에서 `httpx.AsyncClient` / `A2AUpstream` 생성 후
   `app.state` 에 주입 — 라우트는 이 추상만 소비)
4. 라우터 include (`routes.router`)
5. 정적 프론트엔드 마운트

새 agent 를 추가하려면 별도 `A2AUpstream` 인스턴스 + 라우트를 더하면 되고
본 파일의 조립 순서만 수정하면 된다 (OCP).

엔드포인트 / 환경변수 카탈로그는 `user-gateway/README.md`,
SSE 설계는 `user-gateway/docs/sse.md`.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from dev_team_shared.doc_store import DocStoreClient
from dev_team_shared.event_bus import ValkeyEventBus
from dev_team_shared.mcp_client import StreamableMCPClient
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from user_gateway.config import AppConfig, load_config_from_env
from user_gateway.middleware import CacheControlMiddleware
from user_gateway.routes import router as api_router
from user_gateway.upstream import A2AUpstream, ChatProtocolUpstream

# uvicorn 은 자체 logger 만 INFO 로 올리므로 app logger 도 명시적으로 INFO.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

# 정적 자원 기본 위치 — Dockerfile 이 빌드된 frontend/dist 를 여기 복사.
_MODULE_DIR = Path(__file__).resolve().parent
_DEFAULT_STATIC_DIR = _MODULE_DIR.parent.parent / "static"

# 설정은 app 생성 시점에 한 번 로드 — 미들웨어 등록 / lifespan 양쪽에서 공용.
_CONFIG: AppConfig = load_config_from_env()


@asynccontextmanager
async def lifespan(app: FastAPI):
    http = httpx.AsyncClient(
        timeout=httpx.Timeout(
            _CONFIG.upstream.read_timeout_s,
            connect=_CONFIG.upstream.connect_timeout_s,
        ),
        limits=httpx.Limits(
            max_connections=_CONFIG.upstream.max_connections,
            max_keepalive_connections=_CONFIG.upstream.max_keepalive,
        ),
    )
    upstream = A2AUpstream(
        http,
        a2a_url=_CONFIG.upstream.a2a_url,
        card_url=_CONFIG.upstream.card_url,
        connect_retries=_CONFIG.upstream.connect_retries,
        sse_keepalive_s=_CONFIG.sse.keepalive_s,
    )
    chat_upstream = ChatProtocolUpstream(
        http,
        send_url=_CONFIG.upstream.chat_send_url,
        stream_url=_CONFIG.upstream.chat_stream_url,
        connect_retries=_CONFIG.upstream.connect_retries,
        sse_keepalive_s=_CONFIG.sse.keepalive_s,
    )

    # Doc Store MCP — `GET /api/sessions` / `GET /api/history` / `PATCH /api/sessions`
    # (#75 PR 4). FE 측 chat list / hydrate / pinned 갱신용.
    doc_mcp_client = await StreamableMCPClient.connect(
        _CONFIG.upstream.doc_store_mcp_url,
    )
    doc_store = DocStoreClient(doc_mcp_client)

    # event_bus — VALKEY_URL 가 있으면 publish 활성. 없거나 초기화 실패 시 None
    # (routes 의 publish helper 가 no-op).
    event_bus: ValkeyEventBus | None = None
    valkey_url = os.environ.get("VALKEY_URL")
    if valkey_url:
        try:
            event_bus = await ValkeyEventBus.create(valkey_url)
            logger.info("event_bus ready (Valkey at %s)", valkey_url)
        except Exception:
            logger.exception(
                "ValkeyEventBus 초기화 실패 (url=%s) — publish 비활성화",
                valkey_url,
            )

    # 라우트는 app.state 의 추상만 소비 (DIP).
    app.state.config = _CONFIG
    app.state.http = http
    app.state.upstream = upstream
    app.state.chat_upstream = chat_upstream
    app.state.doc_store = doc_store
    app.state.total_timeout_s = _CONFIG.upstream.total_timeout_s
    app.state.event_bus = event_bus

    logger.info(
        "user-gateway ready (primary A2A: %s, total_timeout=%.0fs, "
        "keepalive=%.0fs, pool max_conn=%d)",
        _CONFIG.upstream.a2a_url,
        _CONFIG.upstream.total_timeout_s,
        _CONFIG.sse.keepalive_s,
        _CONFIG.upstream.max_connections,
    )
    try:
        yield
    finally:
        await doc_mcp_client.aclose()
        await http.aclose()
        if event_bus is not None:
            await event_bus.aclose()


app = FastAPI(
    lifespan=lifespan,
    title="User Gateway (dev-team)",
    description="Web UI + A2A 중계 for Primary agent.",
)

# ─── 미들웨어 ────────────────────────────────────────────────────────
if _CONFIG.allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_CONFIG.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    logger.info("CORS enabled for origins: %s", _CONFIG.allowed_origins)

app.add_middleware(CacheControlMiddleware)

# ─── 라우터 ───────────────────────────────────────────────────────────
app.include_router(api_router)

# ─── 정적 프론트엔드 (마지막에 mount — API 경로 우선순위 보장) ──────────
_static_dir = (
    Path(_CONFIG.static_dir) if _CONFIG.static_dir else _DEFAULT_STATIC_DIR
)
if _static_dir.is_dir() and (_static_dir / "index.html").exists():
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="frontend")
    logger.info("serving frontend from %s", _static_dir)
else:
    logger.warning(
        "frontend static dir not found at %s — API only "
        "(run `npm run build` in user-gateway/frontend for local dev)",
        _static_dir,
    )


__all__ = ["app"]
