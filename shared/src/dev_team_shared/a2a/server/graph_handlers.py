"""LangGraph 기반 에이전트용 A2A 메서드 핸들러.

`request.app.state.graph` 에 Compiled LangGraph 가 세팅되어 있다고 가정.
각 에이전트의 server.py 가 lifespan 에서 이 상태를 준비한 뒤 아래 핸들러들을
`make_a2a_router(handlers=[...])` 로 등록하면 된다.

핸들러의 단일 책임:
- A2A `Message` → LangChain `HumanMessage` 번역
- graph.ainvoke / astream 호출
- 결과를 A2A Task / Event Pydantic 모델로 래핑 → JSON-RPC envelope 로 직렬화

FastAPI 결합은 `Request` 객체 하나로 제한 — handler 는 `request.app.state` 에서
자원을 lookup. 생성자 의존성이 없어 에이전트마다 singleton 재사용 가능.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, ClassVar

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from langchain_core.messages import AIMessage, HumanMessage

from dev_team_shared.a2a.events import (
    Artifact,
    Task,
    TaskArtifactUpdateEvent,
    TaskStatus,
    TaskStatusUpdateEvent,
)
from dev_team_shared.a2a.jsonrpc import (
    INVALID_PARAMS,
    rpc_error_response,
    rpc_result_response,
)
from dev_team_shared.a2a.server.handler import MethodHandler
from dev_team_shared.a2a.server.sse import sse_pack, sse_response
from dev_team_shared.a2a.types import Message, Part, Role, TaskState

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  내부 유틸 (A2A ↔ LangChain 메시지 번역 + 에러 포매팅)
# ─────────────────────────────────────────────────────────────────────────────


def _extract_human_text(message: Message) -> str | None:
    """A2A Message 의 text part 들을 줄바꿈으로 join. text 가 없으면 None."""
    parts = [p.text for p in message.parts if p.text is not None]
    if not parts:
        return None
    return "\n".join(parts)


def _stringify_ai_content(content: Any) -> str:
    """AIMessage.content (str 또는 content block 리스트) 에서 text 부분만 추출."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text" and "text" in item:
                out.append(str(item["text"]))
            elif isinstance(item, str):
                out.append(item)
        return "".join(out)
    return str(content)


def _error_detail(exc: BaseException) -> str:
    """예외를 사용자·운영자 친화 문자열로. 흔한 운영 이슈는 힌트 덧붙임."""
    detail = f"{type(exc).__name__}: {exc}"
    if "credit balance" in str(exc).lower():
        detail += (
            " — Anthropic 크레딧 부족 가능성. "
            "https://console.anthropic.com/settings/billing 확인."
        )
    return detail


def _error_reply_message(
    exc: BaseException,
    *,
    context_id: str,
    task_id: str,
) -> Message:
    return Message(
        message_id=f"err-{uuid.uuid4()}",
        role=Role.AGENT,
        parts=[Part(text=_error_detail(exc))],
        context_id=context_id,
        task_id=task_id,
    )


def _parse_message(params: dict[str, Any]) -> Message:
    """params.message 를 Message 로 검증. 실패 시 ValueError."""
    raw = params.get("message")
    if raw is None:
        raise ValueError("missing params.message")
    return Message.model_validate(raw)


# ─────────────────────────────────────────────────────────────────────────────
#  SendMessage — 단방향 요청/응답
# ─────────────────────────────────────────────────────────────────────────────


class GraphSendMessageHandler(MethodHandler):
    """A2A `SendMessage` — 단일 응답.

    `request.app.state.graph.ainvoke(...)` 로 그래프를 한 번 실행하고
    결과의 마지막 AIMessage 를 Task.history 에 포함해 반환.
    """

    method_name: ClassVar[str] = "SendMessage"

    async def handle(
        self,
        request: Request,
        rpc_id: Any,
        params: dict[str, Any],
    ) -> Response:
        try:
            a2a_msg = _parse_message(params)
        except Exception as exc:
            return JSONResponse(
                rpc_error_response(rpc_id, INVALID_PARAMS, f"invalid message: {exc}"),
            )

        human_text = _extract_human_text(a2a_msg)
        if human_text is None:
            return JSONResponse(
                rpc_error_response(rpc_id, INVALID_PARAMS, "no text parts in message"),
            )

        context_id = a2a_msg.context_id or str(uuid.uuid4())
        task_id = f"{context_id}:{uuid.uuid4()}"

        graph = request.app.state.graph
        try:
            result = await graph.ainvoke(
                {"messages": [HumanMessage(content=human_text)]},
                config={"configurable": {"thread_id": context_id}},
            )
        except Exception as exc:
            logger.exception("graph.ainvoke failed in SendMessage")
            task = Task(
                id=task_id,
                context_id=context_id,
                status=TaskStatus(
                    state=TaskState.FAILED,
                    message=_error_reply_message(
                        exc, context_id=context_id, task_id=task_id,
                    ),
                ),
                history=[a2a_msg],
            )
            return JSONResponse(
                rpc_result_response(
                    rpc_id, task.model_dump(by_alias=True, exclude_none=True),
                ),
            )

        ai = next(
            (m for m in reversed(result["messages"]) if isinstance(m, AIMessage)),
            None,
        )
        ai_text = _stringify_ai_content(ai.content) if ai is not None else ""

        agent_reply = Message(
            message_id=f"reply-{uuid.uuid4()}",
            role=Role.AGENT,
            parts=[Part(text=ai_text)],
            context_id=context_id,
            task_id=task_id,
        )
        task = Task(
            id=task_id,
            context_id=context_id,
            status=TaskStatus(state=TaskState.COMPLETED),
            history=[a2a_msg, agent_reply],
        )
        return JSONResponse(
            rpc_result_response(
                rpc_id, task.model_dump(by_alias=True, exclude_none=True),
            ),
        )


# ─────────────────────────────────────────────────────────────────────────────
#  SendStreamingMessage — SSE 스트리밍
# ─────────────────────────────────────────────────────────────────────────────


class GraphSendStreamingMessageHandler(MethodHandler):
    """A2A `SendStreamingMessage` — SSE 로 Task / 이벤트 스트림 반환.

    이벤트 순서:
      1) 초기 `Task(state=TASK_STATE_SUBMITTED)`
      2) N × `TaskArtifactUpdateEvent(append=true, lastChunk=false)`
         — graph.astream(stream_mode="messages") 의 LLM 토큰 chunk 를 래핑
      3) 최종 `TaskStatusUpdateEvent(state=TASK_STATE_COMPLETED, final=true)`

    실패 시 3) 이 `state=TASK_STATE_FAILED` + 에러 메시지로 바뀜.
    """

    method_name: ClassVar[str] = "SendStreamingMessage"

    async def handle(
        self,
        request: Request,
        rpc_id: Any,
        params: dict[str, Any],
    ) -> Response:
        try:
            a2a_msg = _parse_message(params)
        except Exception as exc:
            return JSONResponse(
                rpc_error_response(rpc_id, INVALID_PARAMS, f"invalid message: {exc}"),
            )

        human_text = _extract_human_text(a2a_msg)
        if human_text is None:
            return JSONResponse(
                rpc_error_response(rpc_id, INVALID_PARAMS, "no text parts in message"),
            )

        context_id = a2a_msg.context_id or str(uuid.uuid4())
        task_id = f"{context_id}:{uuid.uuid4()}"
        artifact_id = str(uuid.uuid4())
        graph = request.app.state.graph

        async def event_generator():
            # 1) 초기 Task
            initial = Task(
                id=task_id,
                context_id=context_id,
                status=TaskStatus(state=TaskState.SUBMITTED),
                history=[a2a_msg],
            )
            yield sse_pack(rpc_result_response(
                rpc_id, initial.model_dump(by_alias=True, exclude_none=True),
            ))

            try:
                async for chunk_tuple in graph.astream(
                    {"messages": [HumanMessage(content=human_text)]},
                    config={"configurable": {"thread_id": context_id}},
                    stream_mode="messages",
                ):
                    msg_chunk, _metadata = chunk_tuple
                    if not isinstance(msg_chunk, AIMessage):
                        continue
                    text = _stringify_ai_content(msg_chunk.content)
                    if not text:
                        continue
                    event = TaskArtifactUpdateEvent(
                        task_id=task_id,
                        context_id=context_id,
                        artifact=Artifact(
                            artifact_id=artifact_id,
                            parts=[Part(text=text)],
                        ),
                        append=True,
                        last_chunk=False,
                    )
                    yield sse_pack(rpc_result_response(
                        rpc_id, event.model_dump(by_alias=True, exclude_none=True),
                    ))
            except Exception as exc:
                logger.exception("graph.astream failed in SendStreamingMessage")
                fail_event = TaskStatusUpdateEvent(
                    task_id=task_id,
                    context_id=context_id,
                    status=TaskStatus(
                        state=TaskState.FAILED,
                        message=_error_reply_message(
                            exc, context_id=context_id, task_id=task_id,
                        ),
                    ),
                    final=True,
                )
                yield sse_pack(rpc_result_response(
                    rpc_id, fail_event.model_dump(by_alias=True, exclude_none=True),
                ))
                return

            # 3) 완료 이벤트
            complete = TaskStatusUpdateEvent(
                task_id=task_id,
                context_id=context_id,
                status=TaskStatus(state=TaskState.COMPLETED),
                final=True,
            )
            yield sse_pack(rpc_result_response(
                rpc_id, complete.model_dump(by_alias=True, exclude_none=True),
            ))

        return sse_response(event_generator())


__all__ = [
    "GraphSendMessageHandler",
    "GraphSendStreamingMessageHandler",
]
