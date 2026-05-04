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
from dev_team_shared.a2a.server.graph_handlers.publish import publish_item_append
from dev_team_shared.a2a.server.graph_handlers.session import ChatContext, log_session
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

        ctx = ChatContext.create(
            request,
            rpc_id=rpc_id,
            method=self.method_name,
            context_id=a2a_msg.context_id or str(uuid.uuid4()),
        )

        async with log_session(ctx):
            # 사용자 메시지 publish (item.append role=user)
            await publish_item_append(
                request,
                context_id=ctx.context_id,
                trace_id=ctx.trace_id,
                initiator="user",
                counterpart=ctx.assistant,
                role="user",
                sender="user",
                content=[p.model_dump(mode="json") for p in a2a_msg.parts],
                message_id=a2a_msg.message_id,
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
                return json_response(
                    ctx, make_failed_task(ctx, a2a_msg, agent_timeout_text()),
                )
            except Exception as exc:
                ctx.reason = "graph_error"
                logger.exception("graph.ainvoke failed in SendMessage")
                return json_response(
                    ctx, make_failed_task(ctx, a2a_msg, error_detail(exc)),
                )

            ai_text = extract_ai_reply_text(result)
            # 에이전트 응답 publish (item.append role=agent)
            await publish_item_append(
                request,
                context_id=ctx.context_id,
                trace_id=ctx.trace_id,
                initiator="user",
                counterpart=ctx.assistant,
                role="agent",
                sender=ctx.assistant,
                content=[{"text": ai_text}],
            )
            return json_response(
                ctx,
                make_completed_task(ctx, a2a_msg, ai_text),
            )


__all__ = ["GraphSendMessageHandler"]
