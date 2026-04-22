"""SSE (Server-Sent Events) 헬퍼.

A2A `SendStreamingMessage` 등 SSE 기반 스트리밍 응답을 조립하기 위한 공용 유틸.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterable
from typing import Any

from fastapi.responses import StreamingResponse


def sse_pack(payload: dict[str, Any]) -> str:
    """dict → SSE `data:` 라인 + blank-line 종결자 문자열.

    `ensure_ascii=False` 로 UTF-8 문자(한글 등) 를 이스케이프 없이 그대로 전송.
    """
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def sse_response(generator: AsyncIterable[str]) -> StreamingResponse:
    """SSE 표준 헤더 세팅한 StreamingResponse.

    헤더 의도:
    - `text/event-stream` — SSE 미디어 타입 (EventSource 호환)
    - `Cache-Control: no-cache` — 중간 캐시 방지
    - `X-Accel-Buffering: no` — nginx 등 프록시의 응답 버퍼링 비활성화
    """
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


__all__ = ["sse_pack", "sse_response"]
