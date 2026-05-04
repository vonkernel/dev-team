"""EventProcessor — 이벤트 type 1개 처리 계약 (Strategy + Registry).

새 type 추가 시 본 ABC 를 상속한 concrete 를 작성하고 `processors/__init__.py`
의 `ALL_PROCESSORS` 에 등록만 하면 됨. handler.py / consumer.py 본문 수정 불필요.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, ClassVar

from dev_team_shared.event_bus.events import A2AEvent
from dev_team_shared.mcp_client import StreamableMCPClient


class EventProcessor(ABC):
    """A2A 이벤트 1 type 의 처리 책임.

    `event_type` ClassVar 가 dispatch key. 등록 시 `EventHandler` 가
    `{event_type: processor}` 매핑으로 보관.
    """

    event_type: ClassVar[type[A2AEvent]]

    @abstractmethod
    async def process(self, event: A2AEvent, mcp: StreamableMCPClient) -> None:
        """이벤트 1건을 MCP 호출로 영속화.

        실패 시 raise — consumer 가 PEL 에 남겨 재시도 처리.
        """


# ─────────────────────────────────────────────────────────────────────────────
#  공용 헬퍼 — 모든 processor 가 사용
# ─────────────────────────────────────────────────────────────────────────────


async def call_tool(mcp: StreamableMCPClient, name: str, args: dict[str, Any]) -> Any:
    """MCP 도구 호출 + 응답 JSON parse.

    FastMCP 의 응답 — content[0].text 가 JSON 직렬. None / scalar 도 JSON 가능.
    """
    result = await mcp.call_tool(name, args)
    if not result.content:
        return None
    text = result.content[0].text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


__all__ = ["EventProcessor", "call_tool"]
