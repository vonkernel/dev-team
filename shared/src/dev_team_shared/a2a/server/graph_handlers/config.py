"""SSE / 그래프 호출 자원 관리 튜닝 (#23, docs/sse-connection.md §5).

env override 가능. 운영 환경에서 프록시 idle timeout / LLM 응답 시간에 맞춰
조정한다.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning("invalid %s=%r, falling back to %s", name, raw, default)
        return default


# graph 호출 전체 수명 상한 (S4).
AGENT_TOTAL_TIMEOUT_S: float = _env_float("A2A_AGENT_TOTAL_TIMEOUT_S", 600.0)

# SSE keepalive comment 발송 간격 (S2).
SSE_KEEPALIVE_S: float = _env_float("A2A_SSE_KEEPALIVE_S", 15.0)


__all__ = ["AGENT_TOTAL_TIMEOUT_S", "SSE_KEEPALIVE_S"]
