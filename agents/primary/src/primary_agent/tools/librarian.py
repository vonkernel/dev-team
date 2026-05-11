"""Librarian A2A 채널 LangChain tool — 자연어 정보 검색 / 외부 리소스 조사 위임.

Primary 의 자기 도메인 단순 read 는 Doc Store MCP 직접이 효율적. Librarian 은
**자연어 / 교차 컬렉션 / 외부 리소스 조사** 전용 (#63 분담 모델).

#75 PR 4 commit 12: librarian_query 호출 시 a2a.context.end 발화 — Primary
가 "이 librarian 호출 끝" 이라고 판단하는 시점이 명확 (각 query 가 1회성
조회라 contextId 재사용 X). RPC 라이프사이클이 아닌 *의미상 끝* 발화 — agent
가 결정 (D1).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID, uuid4

from dev_team_shared.a2a.client import A2AClient
from dev_team_shared.a2a.types import Message, Part, Role
from dev_team_shared.event_bus import A2AContextEndEvent, EventBus
from langchain_core.tools import BaseTool, tool

logger = logging.getLogger(__name__)


def build_librarian_tools(
    client: A2AClient,
    *,
    event_bus: EventBus,
) -> list[BaseTool]:
    """Librarian 채널의 1 op — 자연어 위임 + a2a.context.end 발화."""

    @tool
    async def librarian_query(query: str) -> str:
        """Librarian (사서) 에 자연어로 정보 검색 / 외부 리소스 조사 위임.

        사용 시점:
        - Doc Store 의 자연어 / 교차 컬렉션 쿼리 (예: "context X 의 대화 로그")
        - 라이브러리 / 프레임워크 docs (context7)
        - 사용자 제공 URL 페이지 (mcp/web-fetch)
        - 일반 web 검색 (Claude Web Search)

        자기 도메인의 단순 read (식별자 알 때) 는 wiki_pages_* / issues_* 를
        직접 호출하는 게 더 효율적. Librarian 은 자연어 / 교차 / 외부 조사 전용.
        """
        ctx_id = uuid4()
        message = Message(
            message_id=uuid4(),
            role=Role.USER,
            parts=[Part(text=query)],
            context_id=ctx_id,
        )
        # A2AClient 는 sync — async tool 안에서 호출 시 thread offload.
        try:
            result = await asyncio.to_thread(client.send_message, message)
            text = _extract_response_text(result)
        finally:
            # a2a.context.end 발화 — 각 librarian_query 가 1회성 조회라
            # 응답 받은 시점이 곧 "이 inter-agent 대화 끝". RPC 라이프사이클
            # 이 아니라 agent (P) 의 의미적 판단 (D1).
            await _publish_context_end(event_bus, ctx_id, reason="completed")
        return text

    return [librarian_query]


async def _publish_context_end(
    bus: EventBus, context_id: UUID, *, reason: str,
) -> None:
    """a2a.context.end fire-and-forget. runtime 실패만 graceful."""
    try:
        await bus.publish(A2AContextEndEvent(
            context_id=context_id, reason=reason,
        ))
    except Exception:
        logger.exception(
            "publish a2a.context.end failed context_id=%s", context_id,
        )


def _extract_response_text(result: dict[str, Any]) -> str:
    """A2A SendMessage 응답 (Task 또는 Message) 에서 자연어 텍스트 추출.

    응답 형태:
    - Message: `parts: [{text: "..."}]` 직접 반환
    - Task: `status.message.parts[].text` 또는 `artifacts[].parts[].text`

    빈 응답이면 sentinel 반환 ("(no response)").
    """
    pieces: list[str] = []
    for p in result.get("parts") or []:
        if t := p.get("text"):
            pieces.append(t)
    status_msg = (result.get("status") or {}).get("message") or {}
    for p in status_msg.get("parts") or []:
        if t := p.get("text"):
            pieces.append(t)
    for art in result.get("artifacts") or []:
        for p in art.get("parts") or []:
            if t := p.get("text"):
                pieces.append(t)
    return "".join(pieces) or "(no response)"


__all__ = ["build_librarian_tools"]
