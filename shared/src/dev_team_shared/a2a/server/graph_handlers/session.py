"""한 RPC 세션의 식별자 묶음 + lifecycle 로깅 스코프.

핸들러 / 헬퍼 / 팩토리가 동일 `ChatContext` 를 공유하며 `reason` ·
`chunk_count` 를 갱신한다. `log_session` 컨텍스트 매니저는 start / cancel /
end 로그를 자동으로 기록하며, `asyncio.CancelledError` 가 올라오면 `reason`
을 `client_disconnect` 로 갱신한 뒤 그대로 전파한다.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from fastapi import Request

logger = logging.getLogger(__name__)


def _assistant_name(request: Request) -> str:
    """관측 로그용 assistant 이름. `app.state.agent_card.name` 이 있으면 사용."""
    card = getattr(request.app.state, "agent_card", None)
    return getattr(card, "name", "?")


@dataclass
class ChatContext:
    """한 번의 RPC 세션이 갖는 식별자 + 관측 메타.

    `started` 는 wall-clock 이 아닌 `time.monotonic()` 기준 (시계 보정 영향 없음).
    `trace_id` 는 시스템 전체 추적용 (참조: `dev_team_shared.a2a.tracing`).
    """

    request: Request
    rpc_id: Any
    method: str
    assistant: str
    context_id: str
    task_id: str
    artifact_id: str
    trace_id: str
    started: float = field(default_factory=time.monotonic)
    chunk_count: int = 0
    reason: str = "completed"

    @classmethod
    def create(
        cls,
        request: Request,
        *,
        rpc_id: Any,
        method: str,
        context_id: str,
    ) -> ChatContext:
        # trace_id 는 router 가 헤더 또는 신규 발급으로 미리 채워둠 (필수).
        trace_id = getattr(request.state, "trace_id", None)
        if not trace_id:
            # 라우터를 거치지 않는 직접 호출 등의 fallback (테스트 / 비정상 경로).
            trace_id = str(uuid.uuid4())
        return cls(
            request=request,
            rpc_id=rpc_id,
            method=method,
            assistant=_assistant_name(request),
            context_id=context_id,
            task_id=f"{context_id}:{uuid.uuid4()}",
            artifact_id=str(uuid.uuid4()),
            trace_id=trace_id,
        )


@asynccontextmanager
async def log_session(ctx: ChatContext) -> AsyncIterator[None]:
    """SSE / RPC 세션 lifecycle 로깅 스코프.

    enter → start 로그. 정상 / 예외 종료 → end 로그 (reason · duration_ms ·
    chunks). `asyncio.CancelledError` (Starlette 가 client disconnect 등으로
    task 를 cancel) 발생 시 `reason` 을 `client_disconnect` 로 자동 갱신하고
    cancel 로그를 추가 출력한 뒤 전파.
    """
    logger.info(
        "sse_session.start assistant=%s method=%s context_id=%s trace_id=%s",
        ctx.assistant, ctx.method, ctx.context_id, ctx.trace_id,
    )
    try:
        yield
    except asyncio.CancelledError:
        if ctx.reason == "completed":
            ctx.reason = "client_disconnect"
        logger.info(
            "sse_session.cancel assistant=%s context_id=%s trace_id=%s reason=%s",
            ctx.assistant, ctx.context_id, ctx.trace_id, ctx.reason,
        )
        raise
    finally:
        duration_ms = int((time.monotonic() - ctx.started) * 1000)
        logger.info(
            "sse_session.end assistant=%s method=%s context_id=%s "
            "trace_id=%s reason=%s duration_ms=%d chunks=%d",
            ctx.assistant, ctx.method, ctx.context_id,
            ctx.trace_id, ctx.reason, duration_ms, ctx.chunk_count,
        )


__all__ = ["ChatContext", "log_session"]
