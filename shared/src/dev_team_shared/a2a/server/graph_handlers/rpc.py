"""A2A 한 RPC 호출의 식별자 묶음 + lifecycle 로깅 스코프.

핸들러 / 헬퍼 / 팩토리가 동일 `RPCContext` 를 공유하며 `reason` ·
`chunk_count` 를 갱신한다. `log_rpc` 컨텍스트 매니저는 start / cancel /
end 로그를 자동 기록하며, `asyncio.CancelledError` (Starlette 가 client
disconnect 등으로 task 를 cancel) 발생 시 `reason` 을 `client_disconnect` 로
갱신한 뒤 그대로 전파한다.

#75 어휘 — 본 모듈은 한 RPC 호출 스코프이지 chat session / a2a context 가
아니다. session = chat tier (UG↔P/A 의 한 대화창), a2a context = 다중 RPC
를 묶는 namespace. 한 RPC 는 그 둘과 라이프사이클이 다르므로 본 모듈은
publish 책임 0 — 순수 로깅. context.start / task.create 등 wire-level
이벤트 publish 는 핸들러 본체 (send_message / send_streaming) 안에서.
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
class RPCContext:
    """A2A 한 RPC 호출이 갖는 식별자 + 관측 메타.

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
    # 스트리밍 응답 누적 — send_streaming 이 stream 종료 후 단일 message.append publish
    accumulated_response: list[str] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        request: Request,
        *,
        rpc_id: Any,
        method: str,
        context_id: str,
    ) -> RPCContext:
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
async def log_rpc(ctx: RPCContext) -> AsyncIterator[None]:
    """A2A RPC 호출 lifecycle 로깅 스코프 — 순수 로깅 (publish 책임 X).

    enter → `a2a_rpc.start` 로그.
    정상 / 예외 종료 → `a2a_rpc.end` 로그 (reason · duration · chunks).
    `asyncio.CancelledError` 발생 시 `reason` 을 `client_disconnect` 로 갱신한
    뒤 `a2a_rpc.cancel` 로그를 남기고 그대로 전파.

    #75: a2a.context.* / a2a.task.* publish 는 본 함수에서 하지 않는다.
    이유 — RPC 라이프사이클과 a2a context 라이프사이클이 다르기 때문 (한
    contextId 위에 여러 RPC = 여러 Task 가 누적). publish 책임은 핸들러 본체
    (send_message / send_streaming) 의 task lifecycle 흐름 안.
    """
    logger.info(
        "a2a_rpc.start assistant=%s method=%s context_id=%s trace_id=%s",
        ctx.assistant, ctx.method, ctx.context_id, ctx.trace_id,
    )
    try:
        yield
    except asyncio.CancelledError:
        if ctx.reason == "completed":
            ctx.reason = "client_disconnect"
        logger.info(
            "a2a_rpc.cancel assistant=%s context_id=%s trace_id=%s reason=%s",
            ctx.assistant, ctx.context_id, ctx.trace_id, ctx.reason,
        )
        raise
    finally:
        duration_ms = int((time.monotonic() - ctx.started) * 1000)
        logger.info(
            "a2a_rpc.end assistant=%s method=%s context_id=%s "
            "trace_id=%s reason=%s duration_ms=%d chunks=%d",
            ctx.assistant, ctx.method, ctx.context_id,
            ctx.trace_id, ctx.reason, duration_ms, ctx.chunk_count,
        )


__all__ = ["RPCContext", "log_rpc"]
