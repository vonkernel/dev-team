"""A2A `SendStreamingMessage` — SSE 로 Task / 이벤트 스트림 반환.

이벤트 순서:
  1) 초기 `Task(state=TASK_STATE_SUBMITTED)`
  2) N × `TaskArtifactUpdateEvent(append=true, lastChunk=false)`
     — graph.astream(stream_mode="messages") 의 LLM 토큰 chunk 를 래핑
  3) 최종 `TaskStatusUpdateEvent(state=COMPLETED|FAILED, final=true)`

하드닝 (#23): S1 disconnect polling · S2 keepalive · S3 lifecycle 로깅 ·
S4 total timeout 모두 본 경로에 적용.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any, ClassVar

import anyio
from fastapi import Request
from fastapi.responses import JSONResponse, Response

from dev_team_shared.a2a.server.graph_handlers.config import AGENT_TOTAL_TIMEOUT_S
from dev_team_shared.a2a.server.graph_handlers.envelope import sse
from dev_team_shared.a2a.server.graph_handlers.factories import (
    agent_timeout_text,
    error_detail,
    make_completed_status_event,
    make_failed_status_event,
    make_initial_task,
)
from dev_team_shared.a2a.server.graph_handlers.parse import parse_request_or_error
from dev_team_shared.a2a.server.graph_handlers.session import ChatContext, log_session
from dev_team_shared.a2a.server.graph_handlers.stream import stream_artifact_events
from dev_team_shared.a2a.server.handler import MethodHandler
from dev_team_shared.a2a.server.sse import sse_response

logger = logging.getLogger(__name__)


class GraphSendStreamingMessageHandler(MethodHandler):
    method_name: ClassVar[str] = "SendStreamingMessage"

    async def handle(
        self,
        request: Request,
        rpc_id: Any,
        params: dict[str, Any],
    ) -> Response:
        parsed = parse_request_or_error(rpc_id, params)
        if isinstance(parsed, JSONResponse):
            return parsed
        a2a_msg, human_text = parsed

        ctx = ChatContext.create(
            request,
            rpc_id=rpc_id,
            method=self.method_name,
            context_id=a2a_msg.context_id or str(uuid.uuid4()),
        )
        graph = request.app.state.graph

        async def event_generator() -> AsyncIterator[str]:
            async with log_session(ctx):
                yield sse(ctx, make_initial_task(ctx, a2a_msg))
                try:
                    with anyio.fail_after(AGENT_TOTAL_TIMEOUT_S):  # S4
                        async for line in stream_artifact_events(
                            graph, human_text, ctx,
                        ):
                            yield line
                except TimeoutError:
                    ctx.reason = "total_timeout"
                    logger.warning(
                        "graph.astream total timeout (>%ss) in SendStreamingMessage",
                        int(AGENT_TOTAL_TIMEOUT_S),
                    )
                    yield sse(
                        ctx,
                        make_failed_status_event(ctx, agent_timeout_text()),
                    )
                    return
                except asyncio.CancelledError:
                    # log_session 의 CancelledError 핸들러가 reason 갱신 +
                    # 로그 + 정리 수행. 여기선 그대로 전파만.
                    raise
                except Exception as exc:
                    ctx.reason = "graph_error"
                    logger.exception("graph.astream failed in SendStreamingMessage")
                    yield sse(
                        ctx,
                        make_failed_status_event(ctx, error_detail(exc)),
                    )
                    return
                yield sse(ctx, make_completed_status_event(ctx))

        return sse_response(event_generator())


__all__ = ["GraphSendStreamingMessageHandler"]
