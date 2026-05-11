"""A2A `SendMessage` — 동기 응답 (Message 또는 Task wrap).

#75 PR 3: graph 가 채운 `requires_task` hint 보고 응답 shape 분기.

- `requires_task=False` (또는 누락) → Message only. a2a.message.append (user) +
  a2a.message.append (agent) publish, a2a.task.* 발화 X.
- `requires_task=True` → Task wrap. 기존대로 task.create + status_update +
  message.append (task_id 채움) 시퀀스.

분기 결정은 graph 안 LLM 추론 (룰 / 휴리스틱 X). 자세한 정책은
`shared/a2a/messaging.md` §3.4.
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
    make_agent_error_message,
    make_agent_reply_message,
    make_completed_task,
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
from dev_team_shared.a2a.types import Message

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
            # context.start 는 항상 publish (CHR idempotent dedup).
            # message / task publish 는 graph 결과의 requires_task hint 본 뒤 분기.
            await publish_a2a_context_start(
                request,
                context_id=ctx.context_id,
                trace_id=ctx.trace_id,
                initiator_agent="user",   # PR 4 에서 chat tier 분리 시 정확화
                counterpart_agent=ctx.assistant,
                topic=ctx.method,
            )

            try:
                with anyio.fail_after(AGENT_TOTAL_TIMEOUT_S):
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
                return _failed_response(
                    request, ctx, a2a_msg, agent_timeout_text(),
                )
            except Exception as exc:
                ctx.reason = "graph_error"
                logger.exception("graph.ainvoke failed in SendMessage")
                return _failed_response(
                    request, ctx, a2a_msg, error_detail(exc),
                )

            ai_text = extract_ai_reply_text(result)
            requires_task = bool(result.get("requires_task", False))

            # 사용자 메시지 publish — Message only 든 Task wrap 이든 항상.
            # Task wrap 인 경우 task.create 가 먼저 publish 되어야 message 가
            # task_id 로 backlink 가능 → Task 분기에서 task.create 먼저.
            if requires_task:
                return await _respond_with_task(
                    request, ctx, a2a_msg, ai_text,
                )
            return await _respond_with_message(
                request, ctx, a2a_msg, ai_text,
            )


async def _respond_with_message(
    request: Request,
    ctx: RPCContext,
    user_msg: Message,
    ai_text: str,
) -> Response:
    """Message only — task_id 비운 채로 user / agent 메시지 publish."""
    await publish_a2a_message_append(
        request,
        context_id=ctx.context_id,
        message_id=user_msg.message_id,
        role="user",
        sender="user",
        content=[p.model_dump(mode="json") for p in user_msg.parts],
    )
    reply = make_agent_reply_message(ctx, ai_text)
    await publish_a2a_message_append(
        request,
        context_id=ctx.context_id,
        message_id=reply.message_id,
        role="agent",
        sender=ctx.assistant,
        content=[{"text": ai_text}],
    )
    return json_response(ctx, reply)


async def _respond_with_task(
    request: Request,
    ctx: RPCContext,
    user_msg: Message,
    ai_text: str,
) -> Response:
    """Task wrap — task.create → user message → WORKING → agent reply → COMPLETED."""
    await publish_a2a_task_create(
        request,
        context_id=ctx.context_id,
        task_id=ctx.task_id,
        state="SUBMITTED",
    )
    await publish_a2a_message_append(
        request,
        context_id=ctx.context_id,
        message_id=user_msg.message_id,
        task_id=ctx.task_id,
        role="user",
        sender="user",
        content=[p.model_dump(mode="json") for p in user_msg.parts],
    )
    await publish_a2a_task_status_update(
        request, task_id=ctx.task_id, state="WORKING",
    )
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
    return json_response(ctx, make_completed_task(ctx, user_msg, ai_text))


def _failed_response(
    request: Request,
    ctx: RPCContext,
    user_msg: Message,
    error_text: str,
) -> Response:
    """에러 응답 — Task wrap 결정 전 / 결정 실패 시점이라 보수적으로 Message 만.

    graph 호출 자체가 실패했으므로 requires_task hint 가 없음. Task 라이프
    사이클 (SUBMITTED → FAILED) 을 publish 하지 않고 단순 에러 Message 반환.
    """
    err = make_agent_error_message(ctx, error_text)
    return json_response(ctx, err)


__all__ = ["GraphSendMessageHandler"]
