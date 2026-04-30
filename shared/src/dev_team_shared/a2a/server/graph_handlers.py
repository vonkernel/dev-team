"""LangGraph 기반 에이전트용 A2A 메서드 핸들러.

`request.app.state.graph` 에 Compiled LangGraph 가 세팅되어 있다고 가정.
각 에이전트의 server.py 가 lifespan 에서 이 상태를 준비한 뒤 아래 핸들러들을
`make_a2a_router(handlers=[...])` 로 등록하면 된다.

한 RPC 세션은 식별자 묶음(`_ChatContext`) + lifecycle 스코프(`_log_session`)
위에서 흐른다. 핸들러는 ctx 를 만들고 lifecycle 스코프 안에서 graph 를 호출한
뒤, 그 결과를 A2A Task / Event 모델로 조립(`_make_*`)해 envelope 헬퍼
(`_rpc_result` · `_sse` · `_json_response`)로 직렬화해 내보낸다. 스트리밍
경로는 `_stream_artifact_events` 가 graph.astream 을 SSE 라인으로 번역하면서
client disconnect 폴링과 keepalive sentinel 처리를 함께 수행한다.

SSE 자원 관리 정책 (#23, S1~S4) 은 `docs/sse-connection.md` 참조.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, ClassVar

import anyio
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
from dev_team_shared.a2a.server.sse import (
    KEEPALIVE_SENTINEL,
    aiter_with_keepalive,
    sse_pack,
    sse_response,
)
from dev_team_shared.a2a.types import Message, Part, Role, TaskState

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  하드닝 튜닝 (#23 — docs/sse-connection.md §5)
# ─────────────────────────────────────────────────────────────────────────────


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning("invalid %s=%r, falling back to %s", name, raw, default)
        return default


# graph 호출 전체 수명 상한 (S4).
_AGENT_TOTAL_TIMEOUT_S: float = _env_float("A2A_AGENT_TOTAL_TIMEOUT_S", 600.0)

# SSE keepalive comment 발송 간격 (S2).
_SSE_KEEPALIVE_S: float = _env_float("A2A_SSE_KEEPALIVE_S", 15.0)


# ─────────────────────────────────────────────────────────────────────────────
#  세션 컨텍스트 + lifecycle 로깅
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class _ChatContext:
    """한 번의 RPC 세션이 갖는 식별자 + 관측 메타.

    핸들러 / 헬퍼 / 팩토리가 동일 ctx 를 공유하며 `reason` · `chunk_count` 를 갱신.
    `started` 는 wall-clock 이 아닌 `time.monotonic()` 기준 (시계 보정에 영향 없음).
    """

    request: Request
    rpc_id: Any
    method: str
    assistant: str
    context_id: str
    task_id: str
    artifact_id: str
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
    ) -> _ChatContext:
        return cls(
            request=request,
            rpc_id=rpc_id,
            method=method,
            assistant=_assistant_name(request),
            context_id=context_id,
            task_id=f"{context_id}:{uuid.uuid4()}",
            artifact_id=str(uuid.uuid4()),
        )


@asynccontextmanager
async def _log_session(ctx: _ChatContext) -> AsyncIterator[None]:
    """SSE / RPC 세션 lifecycle 로깅.

    수명: enter → start 로그, 정상 / 예외 종료 → end 로그 (reason / duration / chunks).
    `asyncio.CancelledError` (Starlette 가 client disconnect 등으로 task 를 cancel)
    가 발생하면 `reason` 을 `client_disconnect` 로 자동 갱신 후 cancel 로그 추가
    출력하고 그대로 전파 (정리는 `finally` 가 수행).
    """
    logger.info(
        "sse_session.start assistant=%s method=%s context_id=%s",
        ctx.assistant, ctx.method, ctx.context_id,
    )
    try:
        yield
    except asyncio.CancelledError:
        if ctx.reason == "completed":
            ctx.reason = "client_disconnect"
        logger.info(
            "sse_session.cancel assistant=%s context_id=%s reason=%s",
            ctx.assistant, ctx.context_id, ctx.reason,
        )
        raise
    finally:
        duration_ms = int((time.monotonic() - ctx.started) * 1000)
        logger.info(
            "sse_session.end assistant=%s method=%s context_id=%s "
            "reason=%s duration_ms=%d chunks=%d",
            ctx.assistant, ctx.method, ctx.context_id,
            ctx.reason, duration_ms, ctx.chunk_count,
        )


# ─────────────────────────────────────────────────────────────────────────────
#  공통 헬퍼
# ─────────────────────────────────────────────────────────────────────────────


def _assistant_name(request: Request) -> str:
    """관측 로그용 assistant 이름. `app.state.agent_card.name` 이 있으면 사용."""
    card = getattr(request.app.state, "agent_card", None)
    return getattr(card, "name", "?")


async def _is_disconnected(request: Request) -> bool:
    """`request.is_disconnected()` 의 안전 wrapper. 예외 발생 시 False."""
    try:
        return await request.is_disconnected()
    except Exception:
        return False


def _parse_message(params: dict[str, Any]) -> Message:
    raw = params.get("message")
    if raw is None:
        raise ValueError("missing params.message")
    return Message.model_validate(raw)


def _extract_human_text(message: Message) -> str | None:
    """A2A Message 의 text part 들을 줄바꿈 join. text 가 없으면 None."""
    parts = [p.text for p in message.parts if p.text is not None]
    if not parts:
        return None
    return "\n".join(parts)


def _stringify_ai_content(content: Any) -> str:
    """AIMessage.content (str 또는 content block 리스트) 에서 text 만 추출."""
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


def _extract_ai_reply_text(result: dict[str, Any]) -> str:
    """graph.ainvoke 결과의 마지막 AIMessage 의 text 추출."""
    ai = next(
        (m for m in reversed(result["messages"]) if isinstance(m, AIMessage)),
        None,
    )
    return _stringify_ai_content(ai.content) if ai is not None else ""


def _error_detail(exc: BaseException) -> str:
    """예외를 사용자·운영자 친화 문자열로. 흔한 운영 이슈 힌트 포함."""
    detail = f"{type(exc).__name__}: {exc}"
    if "credit balance" in str(exc).lower():
        detail += (
            " — Anthropic 크레딧 부족 가능성. "
            "https://console.anthropic.com/settings/billing 확인."
        )
    return detail


def _agent_timeout_text() -> str:
    return f"agent total timeout after {int(_AGENT_TOTAL_TIMEOUT_S)}s"


def _parse_request_or_error(
    rpc_id: Any,
    params: dict[str, Any],
) -> tuple[Message, str] | JSONResponse:
    """params 검증·번역. 성공: `(a2a_msg, human_text)`, 실패: JSON-RPC 에러 응답."""
    try:
        a2a_msg = _parse_message(params)
    except Exception as exc:
        return JSONResponse(
            rpc_error_response(rpc_id, INVALID_PARAMS, f"invalid message: {exc}"),
        )
    text = _extract_human_text(a2a_msg)
    if text is None:
        return JSONResponse(
            rpc_error_response(rpc_id, INVALID_PARAMS, "no text parts in message"),
        )
    return a2a_msg, text


# ─────────────────────────────────────────────────────────────────────────────
#  A2A Task / Event 팩토리 — model 조립만 담당 (직렬화 / 송신 X)
# ─────────────────────────────────────────────────────────────────────────────


def _error_message(ctx: _ChatContext, text: str) -> Message:
    return Message(
        message_id=f"err-{uuid.uuid4()}",
        role=Role.AGENT,
        parts=[Part(text=text)],
        context_id=ctx.context_id,
        task_id=ctx.task_id,
    )


def _make_initial_task(ctx: _ChatContext, user_msg: Message) -> Task:
    return Task(
        id=ctx.task_id,
        context_id=ctx.context_id,
        status=TaskStatus(state=TaskState.SUBMITTED),
        history=[user_msg],
    )


def _make_completed_task(
    ctx: _ChatContext, user_msg: Message, ai_text: str,
) -> Task:
    agent_reply = Message(
        message_id=f"reply-{uuid.uuid4()}",
        role=Role.AGENT,
        parts=[Part(text=ai_text)],
        context_id=ctx.context_id,
        task_id=ctx.task_id,
    )
    return Task(
        id=ctx.task_id,
        context_id=ctx.context_id,
        status=TaskStatus(state=TaskState.COMPLETED),
        history=[user_msg, agent_reply],
    )


def _make_failed_task(
    ctx: _ChatContext, user_msg: Message, error_text: str,
) -> Task:
    return Task(
        id=ctx.task_id,
        context_id=ctx.context_id,
        status=TaskStatus(
            state=TaskState.FAILED,
            message=_error_message(ctx, error_text),
        ),
        history=[user_msg],
    )


def _make_completed_status_event(ctx: _ChatContext) -> TaskStatusUpdateEvent:
    return TaskStatusUpdateEvent(
        task_id=ctx.task_id,
        context_id=ctx.context_id,
        status=TaskStatus(state=TaskState.COMPLETED),
        final=True,
    )


def _make_failed_status_event(
    ctx: _ChatContext, error_text: str,
) -> TaskStatusUpdateEvent:
    return TaskStatusUpdateEvent(
        task_id=ctx.task_id,
        context_id=ctx.context_id,
        status=TaskStatus(
            state=TaskState.FAILED,
            message=_error_message(ctx, error_text),
        ),
        final=True,
    )


def _make_artifact_event(
    ctx: _ChatContext, text: str,
) -> TaskArtifactUpdateEvent:
    return TaskArtifactUpdateEvent(
        task_id=ctx.task_id,
        context_id=ctx.context_id,
        artifact=Artifact(
            artifact_id=ctx.artifact_id,
            parts=[Part(text=text)],
        ),
        append=True,
        last_chunk=False,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  RPC envelope 직렬화
# ─────────────────────────────────────────────────────────────────────────────


def _rpc_result(ctx: _ChatContext, model: Any) -> dict[str, Any]:
    """Pydantic 모델을 JSON-RPC 2.0 result 응답 dict 로."""
    return rpc_result_response(
        ctx.rpc_id, model.model_dump(by_alias=True, exclude_none=True),
    )


def _sse(ctx: _ChatContext, model: Any) -> str:
    """Pydantic 모델을 SSE `data:` 라인 문자열로."""
    return sse_pack(_rpc_result(ctx, model))


def _json_response(ctx: _ChatContext, model: Any) -> JSONResponse:
    """Pydantic 모델을 단방향 JSON-RPC 응답으로."""
    return JSONResponse(_rpc_result(ctx, model))


# ─────────────────────────────────────────────────────────────────────────────
#  SendMessage (단방향)
# ─────────────────────────────────────────────────────────────────────────────


class GraphSendMessageHandler(MethodHandler):
    """A2A `SendMessage` — 단일 응답.

    `graph.ainvoke(...)` 한 번으로 LLM 응답을 받아 Task 로 감싸 반환.
    """

    method_name: ClassVar[str] = "SendMessage"

    async def handle(
        self,
        request: Request,
        rpc_id: Any,
        params: dict[str, Any],
    ) -> Response:
        parsed = _parse_request_or_error(rpc_id, params)
        if isinstance(parsed, JSONResponse):
            return parsed
        a2a_msg, human_text = parsed

        ctx = _ChatContext.create(
            request,
            rpc_id=rpc_id,
            method=self.method_name,
            context_id=a2a_msg.context_id or str(uuid.uuid4()),
        )

        async with _log_session(ctx):
            try:
                with anyio.fail_after(_AGENT_TOTAL_TIMEOUT_S):  # S4
                    result = await request.app.state.graph.ainvoke(
                        {"messages": [HumanMessage(content=human_text)]},
                        config={"configurable": {"thread_id": ctx.context_id}},
                    )
            except TimeoutError:
                ctx.reason = "total_timeout"
                logger.warning(
                    "graph.ainvoke total timeout (>%ss) in SendMessage",
                    int(_AGENT_TOTAL_TIMEOUT_S),
                )
                return _json_response(
                    ctx, _make_failed_task(ctx, a2a_msg, _agent_timeout_text()),
                )
            except Exception as exc:
                ctx.reason = "graph_error"
                logger.exception("graph.ainvoke failed in SendMessage")
                return _json_response(
                    ctx, _make_failed_task(ctx, a2a_msg, _error_detail(exc)),
                )

            return _json_response(
                ctx,
                _make_completed_task(ctx, a2a_msg, _extract_ai_reply_text(result)),
            )


# ─────────────────────────────────────────────────────────────────────────────
#  SendStreamingMessage (SSE)
# ─────────────────────────────────────────────────────────────────────────────


class GraphSendStreamingMessageHandler(MethodHandler):
    """A2A `SendStreamingMessage` — SSE 로 Task / 이벤트 스트림 반환.

    이벤트 순서:
      1) 초기 `Task(state=TASK_STATE_SUBMITTED)`
      2) N × `TaskArtifactUpdateEvent(append=true, lastChunk=false)`
         — graph.astream(stream_mode="messages") 의 LLM 토큰 chunk 를 래핑
      3) 최종 `TaskStatusUpdateEvent(state=COMPLETED|FAILED, final=true)`

    하드닝 (#23): S1 disconnect polling · S2 keepalive · S3 lifecycle 로깅 ·
    S4 total timeout 모두 본 핸들러에 적용. 자세한 분리는 모듈 docstring 참조.
    """

    method_name: ClassVar[str] = "SendStreamingMessage"

    async def handle(
        self,
        request: Request,
        rpc_id: Any,
        params: dict[str, Any],
    ) -> Response:
        parsed = _parse_request_or_error(rpc_id, params)
        if isinstance(parsed, JSONResponse):
            return parsed
        a2a_msg, human_text = parsed

        ctx = _ChatContext.create(
            request,
            rpc_id=rpc_id,
            method=self.method_name,
            context_id=a2a_msg.context_id or str(uuid.uuid4()),
        )
        graph = request.app.state.graph

        async def event_generator() -> AsyncIterator[str]:
            async with _log_session(ctx):
                yield _sse(ctx, _make_initial_task(ctx, a2a_msg))
                try:
                    with anyio.fail_after(_AGENT_TOTAL_TIMEOUT_S):  # S4
                        async for line in _stream_artifact_events(
                            graph, human_text, ctx,
                        ):
                            yield line
                except TimeoutError:
                    ctx.reason = "total_timeout"
                    logger.warning(
                        "graph.astream total timeout (>%ss) in SendStreamingMessage",
                        int(_AGENT_TOTAL_TIMEOUT_S),
                    )
                    yield _sse(
                        ctx,
                        _make_failed_status_event(ctx, _agent_timeout_text()),
                    )
                    return
                except asyncio.CancelledError:
                    # _log_session 의 CancelledError 핸들러가 reason 갱신 +
                    # 로그 + 정리 수행. 여기선 그대로 전파만.
                    raise
                except Exception as exc:
                    ctx.reason = "graph_error"
                    logger.exception("graph.astream failed in SendStreamingMessage")
                    yield _sse(
                        ctx,
                        _make_failed_status_event(ctx, _error_detail(exc)),
                    )
                    return
                yield _sse(ctx, _make_completed_status_event(ctx))

        return sse_response(event_generator())


async def _stream_artifact_events(
    graph: Any,
    human_text: str,
    ctx: _ChatContext,
) -> AsyncIterator[str]:
    """graph.astream 소비 → keepalive comment / artifact-update SSE 라인 yield.

    매 iteration 시 `request.is_disconnected()` 폴링 (S1). 끊김 감지 시 ctx.reason
    을 갱신한 뒤 정상 종료 (return) — CancelledError 와는 별개의 협조적 cancel
    경로. KEEPALIVE_SENTINEL 수신 시 `:keepalive\\n\\n` comment 만 발송 (S2).
    chunk 수신 시 ctx.chunk_count 증가 + artifact-update SSE 라인 yield.
    """
    async for item in aiter_with_keepalive(
        graph.astream(
            {"messages": [HumanMessage(content=human_text)]},
            config={"configurable": {"thread_id": ctx.context_id}},
            stream_mode="messages",
        ),
        keepalive_s=_SSE_KEEPALIVE_S,
    ):
        if await _is_disconnected(ctx.request):
            ctx.reason = "client_disconnect"
            return
        if item is KEEPALIVE_SENTINEL:
            yield ":keepalive\n\n"
            continue
        msg_chunk, _metadata = item
        if not isinstance(msg_chunk, AIMessage):
            continue
        text = _stringify_ai_content(msg_chunk.content)
        if not text:
            continue
        ctx.chunk_count += 1
        yield _sse(ctx, _make_artifact_event(ctx, text))


__all__ = [
    "GraphSendMessageHandler",
    "GraphSendStreamingMessageHandler",
]
