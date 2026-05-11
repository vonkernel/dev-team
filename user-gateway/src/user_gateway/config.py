"""환경변수 기반 UG 설정.

모든 튜닝 값은 env override 가능. `AppConfig` 는 frozen dataclass —
런타임에 변경되지 않는다는 계약.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    return int(_env_float(name, float(default)))


def _env_list(name: str) -> list[str]:
    raw = os.environ.get(name, "").strip()
    return [o.strip() for o in raw.split(",") if o.strip()]


@dataclass(frozen=True)
class UpstreamConfig:
    """UG → Primary upstream 통신 튜닝.

    A2A endpoint 은 `/api/agent-card` proxy 용도로 유지. chat 트래픽은
    chat_send_url / chat_stream_url (chat protocol — #75 PR 4).
    """

    a2a_url: str
    card_url: str
    chat_send_url: str
    chat_stream_url: str
    doc_store_mcp_url: str
    read_timeout_s: float
    connect_timeout_s: float
    total_timeout_s: float
    max_connections: int
    max_keepalive: int
    connect_retries: int


@dataclass(frozen=True)
class SSEConfig:
    """UG → 브라우저 SSE 동작 튜닝."""

    keepalive_s: float
    disconnect_poll_s: float


@dataclass(frozen=True)
class AppConfig:
    upstream: UpstreamConfig
    sse: SSEConfig
    allowed_origins: list[str] = field(default_factory=list)
    static_dir: str | None = None


def load_config_from_env() -> AppConfig:
    """환경변수를 읽어 `AppConfig` 생성. env 변수 카탈로그는 docstring 참조."""
    return AppConfig(
        upstream=UpstreamConfig(
            a2a_url=os.environ.get(
                "PRIMARY_A2A_URL", "http://primary:8000/a2a/primary",
            ),
            card_url=os.environ.get(
                "PRIMARY_CARD_URL",
                "http://primary:8000/.well-known/agent-card.json",
            ),
            chat_send_url=os.environ.get(
                "PRIMARY_CHAT_SEND_URL", "http://primary:8000/chat/send",
            ),
            chat_stream_url=os.environ.get(
                "PRIMARY_CHAT_STREAM_URL", "http://primary:8000/chat/stream",
            ),
            doc_store_mcp_url=os.environ.get(
                "DOC_STORE_MCP_URL", "http://doc-store-mcp:8000/mcp",
            ),
            read_timeout_s=_env_float("UG_UPSTREAM_READ_TIMEOUT_S", 60.0),
            connect_timeout_s=_env_float("UG_UPSTREAM_CONNECT_TIMEOUT_S", 5.0),
            total_timeout_s=_env_float("UG_UPSTREAM_TOTAL_TIMEOUT_S", 300.0),
            max_connections=_env_int("UG_UPSTREAM_MAX_CONN", 100),
            max_keepalive=_env_int("UG_UPSTREAM_MAX_KEEPALIVE", 20),
            connect_retries=_env_int("UG_UPSTREAM_CONNECT_RETRIES", 2),
        ),
        sse=SSEConfig(
            keepalive_s=_env_float("UG_SSE_KEEPALIVE_S", 15.0),
            disconnect_poll_s=_env_float("UG_SSE_DISCONNECT_POLL_S", 0.5),
        ),
        allowed_origins=_env_list("UG_ALLOWED_ORIGINS"),
        static_dir=os.environ.get("STATIC_DIR"),
    )


__all__ = [
    "AppConfig",
    "SSEConfig",
    "UpstreamConfig",
    "load_config_from_env",
]
