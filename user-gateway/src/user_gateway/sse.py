"""SSE 직렬화 헬퍼 + idle 시 keepalive sentinel.

이 모듈의 책임은 전송 포맷 수준 (SSE `data:` 라인 인코딩 + idle 센티널)에
국한된다. 이벤트 의미 번역은 `translator.py`, upstream I/O 는 `upstream.py`.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any, Final

import anyio
import httpx

KEEPALIVE_SENTINEL: Final = object()
"""`aiter_lines_with_keepalive` 가 idle 시 방출하는 센티널.

호출 측 generator 는 이 값을 받으면 `:keepalive\\n\\n` 라인을 브라우저로 내려
프록시/LB 의 idle timeout 방어를 수행한다.
"""


def sse_pack(payload: dict[str, Any]) -> str:
    """dict → SSE `data:` 라인 + blank-line 종결자. UTF-8 그대로 전송."""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def aiter_lines_with_keepalive(
    response: httpx.Response,
    *,
    keepalive_s: float,
) -> AsyncIterator[str | object]:
    """httpx response 의 line 스트림을 idle 시 `KEEPALIVE_SENTINEL` 로 깨운다.

    `keepalive_s` 초 동안 다음 line 이 안 오면 sentinel 을 yield — 호출 측이
    keepalive comment 를 클라이언트에 발송하거나 disconnect 체크를 수행할 기회.
    """
    iterator = response.aiter_lines()
    while True:
        try:
            with anyio.fail_after(keepalive_s):
                line = await iterator.__anext__()
        except TimeoutError:
            yield KEEPALIVE_SENTINEL
            continue
        except StopAsyncIteration:
            return
        yield line


__all__ = ["KEEPALIVE_SENTINEL", "aiter_lines_with_keepalive", "sse_pack"]
