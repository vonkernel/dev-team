"""A2A upstream 이벤트 ↔ UG 의 브라우저용 단순 이벤트 번역.

**순수 함수 only**. upstream JSON dict 를 받아 브라우저에 내려보낼 UG 이벤트
dict 를 반환. I/O · 상태 · 로깅 부작용 없음 → 단위 테스트가 자명함.

UG 이벤트 스키마는 `user-gateway/docs/sse.md` §5 정의.
A2A → UG 매핑 규칙은 동 문서 §6.
"""

from __future__ import annotations

import json
from typing import Any


def parse_a2a_line(line: str) -> dict[str, Any] | None:
    """SSE `data: {...}` 라인 → dict. 비 data 라인 / 파싱 실패 시 `None`."""
    if not line or not line.startswith("data:"):
        return None
    try:
        return json.loads(line[5:].strip())
    except json.JSONDecodeError:
        return None


def translate(payload: dict[str, Any]) -> dict[str, Any] | None:
    """A2A JSON-RPC 이벤트 payload → UG 단순 이벤트 dict.

    반환 값이 `None` 이면 UI 에 노출할 필요 없는 이벤트 (예: 초기 `task`).

    규칙 (sse.md §6):
    - rpc `error` envelope              → `{type:"error", message}`
    - `artifact-update` + text part     → `{type:"chunk", text}`
    - `status-update` COMPLETED         → `{type:"done"}`
    - `status-update` FAILED            → `{type:"error", message}`
    - 그 외 (초기 task 등)              → None (무시)
    """
    err = payload.get("error")
    if err:
        return {"type": "error", "message": err.get("message", "rpc error")}

    result = payload.get("result")
    if not isinstance(result, dict):
        return None

    kind = result.get("kind")
    if kind == "artifact-update":
        text = _extract_first_text(result.get("artifact") or {})
        if text:
            return {"type": "chunk", "text": text}
        return None

    if kind == "status-update":
        state = (result.get("status") or {}).get("state")
        if state == "TASK_STATE_COMPLETED":
            return {"type": "done"}
        if state == "TASK_STATE_FAILED":
            msg = _extract_status_message_text(result.get("status") or {})
            return {"type": "error", "message": msg or "upstream failed"}

    # 초기 `task` 이벤트는 UG 가 별도로 `meta` 를 먼저 방출하므로 여기선 무시.
    return None


def _extract_first_text(artifact: dict[str, Any]) -> str:
    for p in artifact.get("parts") or []:
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


__all__ = ["parse_a2a_line", "translate"]
