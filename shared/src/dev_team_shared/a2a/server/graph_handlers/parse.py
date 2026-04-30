"""A2A 요청 파싱 + LLM 응답 텍스트 추출.

JSON-RPC `params` → `Message` (Pydantic) → human text 까지가 들어오는 방향,
LangGraph `ainvoke` 결과 → 마지막 `AIMessage` text 가 나가는 방향.
"""

from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse
from langchain_core.messages import AIMessage

from dev_team_shared.a2a.jsonrpc import INVALID_PARAMS, rpc_error_response
from dev_team_shared.a2a.types import Message


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


def stringify_ai_content(content: Any) -> str:
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


def extract_ai_reply_text(result: dict[str, Any]) -> str:
    """graph.ainvoke 결과의 마지막 AIMessage text 추출."""
    ai = next(
        (m for m in reversed(result["messages"]) if isinstance(m, AIMessage)),
        None,
    )
    return stringify_ai_content(ai.content) if ai is not None else ""


def parse_request_or_error(
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


__all__ = [
    "extract_ai_reply_text",
    "parse_request_or_error",
    "stringify_ai_content",
]
