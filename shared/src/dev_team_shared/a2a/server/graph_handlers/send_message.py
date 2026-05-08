"""A2A `SendMessage` — 단방향 응답.

`graph.ainvoke(...)` 한 번으로 LLM 응답을 받아 Task 로 감싸 반환.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, ClassVar

import anyio
from fastapi import Request
from fastapi.responses import JSONResponse, Response
from langchain_core.messages import HumanMessage

from dev_team_shared.a2a.server.graph_handlers.config import AGENT_TOTAL_TIMEOUT_S
from dev_team_shared.a2a.server.graph_handlers.envelope import json_response
from dev_team_shared.a2a.server.graph_handlers.factories import (
    agent_timeout_text,
    error_detail,
    make_completed_task,
    make_failed_task,
)
from dev_team_shared.a2a.server.graph_handlers.parse import (
    extract_ai_reply_text,
    parse_request_or_error,
)
from dev_team_shared.a2a.server.graph_handlers.publish import (
    publish_a2a_context_start,
    publish_a2a_message_append,
    publish_a2a_task_create,
    publish_a2a_task_status_update,
)
from dev_team_shared.a2a.server.graph_handlers.rpc import RPCContext, log_rpc
from dev_team_shared.a2a.server.handler import MethodHandler

logger = logging.getLogger(__name__)


class GraphSendMessageHandler(MethodHandler):
    method_name: ClassVar[str] = "SendMessage"

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

        ctx = RPCContext.create(
            request,
            rpc_id=rpc_id,
            method=self.method_name,
            context_id=a2a_msg.context_id or str(uuid.uuid4()),
        )

        async with log_rpc(ctx):
            # 이벤트 순서: a2a.context.start (idempotent — CHR 가 dedup) →
            # Task commit → user Message (Task.history) → WORKING 전이.
            # 현재 구현은 모든 SendMessage 응답을 Task wrap (PR 3 에서
            # trivial / stateful 분기로 정정 예정).
            await publish_a2a_context_start(
                request,
                context_id=ctx.context_id,
                trace_id=ctx.trace_id,
                initiator_agent="user",   # PR 4 에서 chat tier 분리 시 정확화
                counterpart_agent=ctx.assistant,
                topic=ctx.method,
            )
            await publish_a2a_task_create(
                request,
                context_id=ctx.context_id,
                task_id=ctx.task_id,
                state="SUBMITTED",
            )
            await publish_a2a_message_append(
                request,
                context_id=ctx.context_id,
                message_id=a2a_msg.message_id,
                task_id=ctx.task_id,
                role="user",
                sender="user",
                content=[p.model_dump(mode="json") for p in a2a_msg.parts],
            )
            await publish_a2a_task_status_update(
                request, task_id=ctx.task_id, state="WORKING",
            )
            try:
                with anyio.fail_after(AGENT_TOTAL_TIMEOUT_S):  # S4
                    result = await request.app.state.graph.ainvoke(
                        {"messages": [HumanMessage(content=human_text)]},
                        config={"configurable": {"thread_id": ctx.context_id}},
                    )
            except TimeoutError:
                ctx.reason = "total_timeout"
                logger.warning(
                    "graph.ainvoke total timeout (>%ss) in SendMessage",
                    int(AGENT_TOTAL_TIMEOUT_S),
                )
                await publish_a2a_task_status_update(
                    request, task_id=ctx.task_id, state="FAILED",
                    reason="total_timeout",
                )
                return json_response(
                    ctx, make_failed_task(ctx, a2a_msg, agent_timeout_text()),
                )
            except Exception as exc:
                ctx.reason = "graph_error"
                logger.exception("graph.ainvoke failed in SendMessage")
                await publish_a2a_task_status_update(
                    request, task_id=ctx.task_id, state="FAILED",
                    reason="graph_error",
                )
                return json_response(
                    ctx, make_failed_task(ctx, a2a_msg, error_detail(exc)),
                )

            ai_text = extract_ai_reply_text(result)
            # 에이전트 응답 publish — Task.history 의 일원 (task_id 채움).
            # message_id 는 PR (별도) 에서 graph 결과의 AIMessage.id 또는 server
            # 발급 UUID 로 정확화 예정. 본 PR 에선 server 발급 UUID 로 임시.
            await publish_a2a_message_append(
                request,
                context_id=ctx.context_id,
                message_id=f"{ctx.assistant}-msg-{uuid.uuid4()}",
                task_id=ctx.task_id,
                role="agent",
                sender=ctx.assistant,
                content=[{"text": ai_text}],
            )
            await publish_a2a_task_status_update(
                request, task_id=ctx.task_id, state="COMPLETED",
            )
            return json_response(
                ctx,
                make_completed_task(ctx, a2a_msg, ai_text),
            )


__all__ = ["GraphSendMessageHandler"]
