"""SSE (Server-Sent Events) 헬퍼.

A2A `SendStreamingMessage` 등 SSE 기반 스트리밍 응답을 조립하기 위한 공용 유틸.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterable, AsyncIterator
from typing import Any, Final

import anyio
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


KEEPALIVE_SENTINEL: Final = object()
"""`aiter_with_keepalive` 가 idle 시 방출하는 센티널.

호출 측은 이 값을 받으면 `:keepalive\\n\\n` comment 라인을 클라이언트로 내려
보내 프록시 / LB 의 idle timeout 방어 + disconnect polling 깨우기를 수행한다.
"""


async def aiter_with_keepalive(
    aiter: AsyncIterable[Any],
    *,
    keepalive_s: float,
) -> AsyncIterator[Any]:
    """임의 async iterator 를 감싸 idle 시 `KEEPALIVE_SENTINEL` 을 yield.

    `keepalive_s` 초 동안 다음 item 이 안 오면 sentinel 을 yield — 호출 측이
    keepalive comment 발송 / disconnect 체크 / 기타 횡단 작업을 수행할 기회를
    얻는다. LangGraph `astream(...)` · httpx `response.aiter_lines()` 등 모든
    async iterator 에 적용 가능.
    """
    iterator = aiter.__aiter__()
    while True:
        try:
            with anyio.fail_after(keepalive_s):
                item = await iterator.__anext__()
        except TimeoutError:
            yield KEEPALIVE_SENTINEL
            continue
        except StopAsyncIteration:
            return
        yield item


__all__ = [
    "KEEPALIVE_SENTINEL",
    "aiter_with_keepalive",
    "sse_pack",
    "sse_response",
]
