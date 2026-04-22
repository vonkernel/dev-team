"""A2A JSON-RPC 메서드 핸들러 추상 인터페이스.

각 에이전트가 지원하는 A2A 메서드(SendMessage, SendStreamingMessage, GetTask, ...)
는 `MethodHandler` 구현체로 표현된다. 라우터는 `method_name` 을 key 로 등록된
핸들러에 디스패치한다.

핸들러는 `JSONResponse`(단방향) 또는 `StreamingResponse`(SSE) 를 반환할 수 있으며,
필요한 런타임 자원(그래프, 체크포인터 등) 은 `request.app.state` 에서 꺼내 쓴다.
이 규약이 핸들러를 FastAPI 라우트와 결합시키지만, 반대로 핸들러 인스턴스 자체는
매 요청 사이에 공유 가능 (stateless).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from fastapi import Request
from fastapi.responses import Response


class MethodHandler(ABC):
    """A2A JSON-RPC 메서드 하나를 처리하는 핸들러.

    구현체는 클래스 속성 `method_name` 을 반드시 지정해야 라우터가 등록한다
    (중복된 메서드 이름은 `make_a2a_router` 에서 에러).

    구현 시 주의:
    - 실제 에이전트 로직(예: `graph.ainvoke`) 을 수행하고, 그 결과를 A2A Task /
      Event 로 **번역** 한 뒤 JSONResponse / StreamingResponse 로 반환.
    - 런타임 자원은 `request.app.state` 에서 lookup (lifespan 에서 세팅됨).
    - HTTP/SSE 포맷 조립은 `dev_team_shared.a2a.jsonrpc` / `.server.sse` 헬퍼 활용.
    """

    method_name: ClassVar[str]

    @abstractmethod
    async def handle(
        self,
        request: Request,
        rpc_id: Any,
        params: dict[str, Any],
    ) -> Response:
        """요청 하나를 처리하여 응답(단방향 or 스트리밍)을 반환."""


__all__ = ["MethodHandler"]
