"""LangGraph `astream` → A2A artifact-update SSE 라인 번역.

매 iteration 시 `request.is_disconnected()` 폴링(S1) — 끊김 감지 시 ctx.reason
을 갱신한 뒤 정상 종료 (`return`). 이는 Starlette 의 `CancelledError` 와는
별개의 협조적 cancel 경로. `KEEPALIVE_SENTINEL` 수신 시 `:keepalive\\n\\n`
comment 만 발송 (S2). chunk 수신 시 ctx.chunk_count 증가 + artifact-update
SSE 라인 yield.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from fastapi import Request
from langchain_core.messages import AIMessage, HumanMessage

from dev_team_shared.a2a.server.sse import KEEPALIVE_SENTINEL, aiter_with_keepalive

from dev_team_shared.a2a.server.graph_handlers.config import SSE_KEEPALIVE_S
from dev_team_shared.a2a.server.graph_handlers.envelope import sse
from dev_team_shared.a2a.server.graph_handlers.factories import make_artifact_event
from dev_team_shared.a2a.server.graph_handlers.parse import stringify_ai_content
from dev_team_shared.a2a.server.graph_handlers.rpc import RPCContext


async def _is_disconnected(request: Request) -> bool:
    """`request.is_disconnected()` 의 안전 wrapper. 예외 발생 시 False."""
    try:
        return await request.is_disconnected()
    except Exception:
        return False


async def stream_artifact_events(
    graph: Any,
    human_text: str,
    ctx: RPCContext,
) -> AsyncIterator[str]:
    """graph.astream 소비 → keepalive comment / artifact-update SSE 라인 yield."""
    async for item in aiter_with_keepalive(
        graph.astream(
            {"messages": [HumanMessage(content=human_text)]},
            config={"configurable": {"thread_id": ctx.context_id}},
            stream_mode="messages",
        ),
        keepalive_s=SSE_KEEPALIVE_S,
    ):
        if await _is_disconnected(ctx.request):
            ctx.reason = "client_disconnect"
            return
        if item is KEEPALIVE_SENTINEL:
            yield ":keepalive\n\n"
            continue
        msg_chunk, metadata = item
        # classify_response 노드 (#75 PR 3 의 A2A 응답 shape 결정 LLM) 의
        # structured output token 은 stream 에서 제외 — 사용자에게 노출되지
        # 않도록. 메인 응답 노드 (`llm_call`) 의 token 만 통과.
        if metadata.get("langgraph_node") == "classify_response":
            continue
        if not isinstance(msg_chunk, AIMessage):
            continue
        text = stringify_ai_content(msg_chunk.content)
        if not text:
            continue
        ctx.chunk_count += 1
        ctx.accumulated_response.append(text)
        yield sse(ctx, make_artifact_event(ctx, text))


__all__ = ["stream_artifact_events"]
