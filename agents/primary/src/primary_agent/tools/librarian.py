"""Librarian A2A 채널 LangChain tool — 자연어 정보 검색 / 외부 리소스 조사 위임.

Primary 의 자기 도메인 단순 read 는 Doc Store MCP 직접이 효율적. Librarian 은
**자연어 / 교차 컬렉션 / 외부 리소스 조사** 전용 (#63 분담 모델).
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

from dev_team_shared.a2a.client import A2AClient
from dev_team_shared.a2a.types import Message, Part, Role
from langchain_core.tools import BaseTool, tool


def build_librarian_tools(client: A2AClient) -> list[BaseTool]:
    """Librarian 채널의 1 op — 자연어 위임."""

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
        message = Message(
            message_id=str(uuid4()),
            role=Role.USER,
            parts=[Part(text=query)],
            context_id=str(uuid4()),
        )
        # A2AClient 는 sync — async tool 안에서 호출 시 thread offload.
        result = await asyncio.to_thread(client.send_message, message)
        return _extract_response_text(result)

    return [librarian_query]


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
