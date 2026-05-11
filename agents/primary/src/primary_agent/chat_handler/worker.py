"""Primary chat session 의 background worker — graph 호출 + SSE 채널 push.

`POST /chat/send` 가 즉시 202 ack 반환 후 `run_session_turn` 을 background
task 로 실행. 본 worker 는:

1. graph.astream 호출 (session_id = thread_id, extra_system_message 주입)
2. classify_response 노드 token 필터 + AIMessage chunks 만 accumulate
3. 누적된 chunks 를 outgoing_send 로 push (FE 에 SSE chunk 이벤트로 흐름)
4. 완료 후 agent 응답을 `chat.append role=agent` publish (D3)
5. SSE 채널에 `message` + `done` 이벤트 emit

실패 (timeout / 일반 예외) 는 SSE `error` 이벤트로 통보. lock 으로 같은
session 의 graph 호출 sequential.
"""

from __future__ import annotations

import logging
import uuid as _uuid
from typing import Any
from uuid import UUID

import anyio
from dev_team_shared.a2a.server.graph_handlers.parse import stringify_ai_content
from dev_team_shared.chat_protocol import ChatEvent, ChatEventType, SessionRuntime
from dev_team_shared.event_bus import ChatAppendEvent, EventBus
from fastapi import Request
from langchain_core.messages import AIMessage, HumanMessage

logger = logging.getLogger(__name__)

# Graph total timeout — A2A handler 의 AGENT_TOTAL_TIMEOUT_S 와 일관.
GRAPH_TIMEOUT_S = 180.0


async def run_session_turn(
    runtime: SessionRuntime,
    request: Request,
    text: str,
    message_id: str,
    prev_chat_id: UUID | None = None,
) -> None:
    """한 turn 의 graph 호출 + SSE push + chat.append publish.

    Entry point — `POST /chat/send` 가 background task 로 spawn.
    runtime.lock 으로 같은 session 의 두 번째 turn 은 sequential 처리.

    `prev_chat_id` 는 UG 가 발급한 user_chat_id — 본 agent 응답의 chats 의
    prev_chat_id 로 사용 (chains the user→agent turn).
    """
    graph = request.app.state.graph
    event_bus: EventBus = request.app.state.event_bus
    # agent_message_id / agent_chat_id 모두 turn 시작 시점에 1회 생성 —
    # chunks / final message / chat.append publish 모두 같은 id 사용
    # (FE 의 'same message_id 면 갱신' 로직과 정합).
    agent_message_id = f"primary-msg-{_uuid.uuid4()}"
    agent_chat_id = _uuid.uuid4()
    async with runtime.lock:
        try:
            with anyio.fail_after(GRAPH_TIMEOUT_S):
                accumulated_text = await _stream_chunks_to_session(
                    graph=graph,
                    runtime=runtime,
                    text=text,
                    agent_message_id=agent_message_id,
                    agent_chat_id=agent_chat_id,
                )
            await _finalize_agent_response(
                runtime=runtime,
                user_message_id=message_id,
                agent_message_id=agent_message_id,
                agent_chat_id=agent_chat_id,
                prev_chat_id=prev_chat_id,
                agent_text=accumulated_text,
                event_bus=event_bus,
            )
        except TimeoutError:
            logger.warning(
                "chat session graph timeout (>%ss) session_id=%s",
                int(GRAPH_TIMEOUT_S), runtime.session_id,
            )
            await _emit_error(runtime, message_id, "graph timeout")
        except Exception as exc:
            logger.exception(
                "chat session graph failed session_id=%s", runtime.session_id,
            )
            await _emit_error(
                runtime, message_id, f"{type(exc).__name__}: {exc}",
            )


# ─────────────────────────────────────────────────────────────────────────────
# Internal — phase 별 helper
# ─────────────────────────────────────────────────────────────────────────────


def _build_graph_input(session_id: UUID, text: str) -> dict[str, Any]:
    """graph.astream input 빌드 — messages + runtime context system 주입.

    `extra_system_message` 는 LLM 이 도구 호출 시 (예: assignment.create) 의
    runtime 정보 (현재 chat session_id) 참조하도록 노출.
    """
    runtime_ctx = (
        f"[runtime] current chat session_id: {session_id}. "
        "When calling tools that accept `root_session_id` (예: "
        "assignment.create), use this value."
    )
    return {
        "messages": [HumanMessage(content=text)],
        "extra_system_message": runtime_ctx,
    }


async def _stream_chunks_to_session(
    *,
    graph: Any,
    runtime: SessionRuntime,
    text: str,
    agent_message_id: str,
    agent_chat_id: UUID,
) -> str:
    """graph.astream 소비 → chunk 이벤트 push → 누적 텍스트 반환.

    chunks payload 의 `message_id` 는 **agent_message_id** — 최종 message
    이벤트와 같은 id 라 FE 가 같은 메시지의 streaming → 완성 으로 누적 갱신.
    `chat_id` 는 agent_chat_id (publisher-supplied, chats.id 와 1:1).

    필터:
    - `classify_response` 노드의 token 은 사용자에게 노출 X (PR 3 의 분기
      결정용 internal LLM)
    - AIMessage 가 아닌 chunk 는 skip (ToolMessage 등)
    - 빈 텍스트 chunk skip
    """
    config = {"configurable": {"thread_id": str(runtime.session_id)}}
    accumulated: list[str] = []
    async for msg_chunk, metadata in graph.astream(
        _build_graph_input(runtime.session_id, text),
        config=config,
        stream_mode="messages",
    ):
        if metadata.get("langgraph_node") == "classify_response":
            continue
        if not isinstance(msg_chunk, AIMessage):
            continue
        text_chunk = stringify_ai_content(msg_chunk.content)
        if not text_chunk:
            continue
        accumulated.append(text_chunk)
        runtime.send(ChatEvent(
            type=ChatEventType.CHUNK,
            payload={
                "text": text_chunk,
                "message_id": agent_message_id,
                "chat_id": str(agent_chat_id),
            },
        ))
    return "".join(accumulated)


async def _finalize_agent_response(
    *,
    runtime: SessionRuntime,
    user_message_id: str,
    agent_message_id: str,
    agent_chat_id: UUID,
    prev_chat_id: UUID | None,
    agent_text: str,
    event_bus: EventBus,
) -> None:
    """graph 완료 후 agent 응답 publish + SSE message/done 이벤트 emit.

    publish (chat.append role=agent) 는 D3 — agent 자기 발화는 자기가
    publish (UG 가 publish 하지 않음). agent_message_id / agent_chat_id 는
    chunks 와 동일 — `run_session_turn` 이 turn 시작 시점에 1회 생성.
    `prev_chat_id` 는 user_chat_id (UG 가 발급해 forward) — chain.
    """
    await _publish_agent_chat(
        event_bus,
        runtime.session_id,
        agent_text,
        agent_message_id,
        agent_chat_id,
        prev_chat_id,
    )
    runtime.send(ChatEvent(
        type=ChatEventType.MESSAGE,
        payload={
            "message_id": agent_message_id,
            "chat_id": str(agent_chat_id),
            "prev_chat_id": str(prev_chat_id) if prev_chat_id else None,
            "role": "agent",
            "text": agent_text,
        },
    ))
    runtime.send(ChatEvent(
        type=ChatEventType.DONE,
        payload={"message_id": user_message_id},
    ))


async def _publish_agent_chat(
    bus: EventBus,
    session_id: UUID,
    text: str,
    message_id: str,
    chat_id: UUID,
    prev_chat_id: UUID | None,
) -> None:
    """`chat.append role=agent` publish (D3 — agent 자기 발화는 자기가).

    runtime publish 실패는 chat 흐름 차단 X — 로그만 (fire-and-forget).
    """
    if not text:
        return
    try:
        await bus.publish(ChatAppendEvent(
            chat_id=chat_id,
            session_id=session_id,
            role="agent",
            sender="primary",
            prev_chat_id=prev_chat_id,
            content=[{"text": text}],
            message_id=message_id,
        ))
    except Exception:
        logger.exception(
            "publish chat.append (agent) failed session_id=%s", session_id,
        )


async def _emit_error(
    runtime: SessionRuntime, message_id: str, detail: str,
) -> None:
    """SSE `error` 이벤트 emit. 실패해도 흐름 차단 X (로그만)."""
    try:
        runtime.send(ChatEvent(
            type=ChatEventType.ERROR,
            payload={"message_id": message_id, "message": detail},
        ))
    except Exception:
        logger.exception(
            "error event send failed (session_id=%s)", runtime.session_id,
        )


__all__ = [
    "GRAPH_TIMEOUT_S",
    "run_session_turn",
]
