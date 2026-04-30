"""SSE (Server-Sent Events) 헬퍼.

A2A `SendStreamingMessage` 등 SSE 기반 스트리밍 응답을 조립하기 위한 공용 유틸.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterable, AsyncIterator
from typing import Any, Final

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

    구현 — **non-cancelling peek 패턴**:
    `asyncio.wait(timeout=...)` 로 다음 item 을 *기다리되 cancel 하지 않고*
    peek. timeout 시 sentinel 만 방출하고 같은 pending task 를 다음 라운드에서
    계속 await. 이 패턴은 비복원형 generator (예: LangGraph `astream`)에서도
    chunk 유실 없이 동작한다 — 단순 `anyio.fail_after` 로 감싸면 timeout 시
    underlying generator 가 cancel 되어 chunk 가 사라진다.
    """
    iterator = aiter.__aiter__()
    pending: asyncio.Task[Any] | None = None
    try:
        while True:
            if pending is None:
                pending = asyncio.ensure_future(iterator.__anext__())
            done, _ = await asyncio.wait({pending}, timeout=keepalive_s)
            if not done:
                # idle — sentinel 만 방출. pending 은 그대로 살려둔 채 다음 라운드.
                yield KEEPALIVE_SENTINEL
                continue
            # pending 완료 — 결과 회수 후 다음 라운드를 위해 None 으로 리셋
            try:
                item = pending.result()
            except StopAsyncIteration:
                pending = None
                return
            pending = None
            yield item
    finally:
        # 외부에서 generator 가 close / cancel 되면 pending task 도 정리
        if pending is not None and not pending.done():
            pending.cancel()
            try:
                await pending
            except BaseException:  # noqa: BLE001 — cleanup; cancelled / 어떤 예외든 무시
                pass


__all__ = [
    "KEEPALIVE_SENTINEL",
    "aiter_with_keepalive",
    "sse_pack",
    "sse_response",
]
