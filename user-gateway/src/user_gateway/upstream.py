"""A2A upstream 어댑터.

UG 가 Primary(또는 향후 다른 agent) 의 A2A 엔드포인트를 호출하는 **단일 책임**
을 가진다. 라우트 핸들러는 이 추상 뒤에서 httpx 를 직접 모른다 (DIP).

OCP 관점:
- 새 agent 가 추가되면 `A2AUpstream` 인스턴스를 하나 더 만들고 (또는 동일 타입
  이 다른 URL 을 가리킨 채) 새 라우트를 마운트하면 된다. 본 클래스 수정 불필요.
- gRPC 같은 다른 transport 가 필요해지면 동일 시그니처의 새 구현체를 만들고
  Protocol / ABC 로 공통 인터페이스를 뽑아 DIP 유지.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

import anyio
import httpx

from user_gateway.sse import aiter_lines_with_keepalive

logger = logging.getLogger(__name__)


class UpstreamHTTPError(RuntimeError):
    """Upstream 이 2xx 이 아닌 응답을 돌려준 경우 (재시도 정책 초과 후)."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(f"upstream HTTP {status_code}: {detail[:100]}")
        self.status_code = status_code
        self.detail = detail


class A2AUpstream:
    """httpx 기반 A2A upstream 어댑터.

    공개 인터페이스 (ISP — 좁고 의도 분명):
        - `fetch_agent_card()` → AgentCard JSON
        - `stream_message(text, context_id)` → AsyncIterator of line or sentinel

    Connect 단계 장애는 지수 backoff 로 재시도 (스트리밍 중간 실패는 재시도 X —
    토큰이 이미 방출되어 멱등하지 않음). idle 시 `aiter_lines_with_keepalive`
    의 KEEPALIVE_SENTINEL 이 함께 흘러나오므로 호출 측이 keepalive comment 를
    클라이언트에 내려보내고 disconnect 를 감지할 수 있다.
    """

    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        a2a_url: str,
        card_url: str,
        connect_retries: int,
        sse_keepalive_s: float,
    ) -> None:
        self._http = http
        self.a2a_url = a2a_url
        self.card_url = card_url
        self._connect_retries = connect_retries
        self._sse_keepalive_s = sse_keepalive_s

    async def fetch_agent_card(self) -> dict[str, Any]:
        r = await self._http.get(self.card_url)
        r.raise_for_status()
        return r.json()

    async def stream_message(
        self,
        text: str,
        context_id: str,
        *,
        message_id: str | None = None,
    ) -> AsyncIterator[str | object]:
        """A2A `SendStreamingMessage` 호출. 결과 SSE line / sentinel 을 yield.

        `message_id` 가 주어지면 A2A Message.messageId 로 사용. 호출자(routes)가
        같은 id 로 event_bus item.append publish → Primary 도 같은 id 사용 →
        CHR 의 message_id dedup 에서 중복 제거.

        Raises:
            UpstreamHTTPError: 재시도 소진 후에도 비-200 응답.
            httpx.ConnectError / httpx.ConnectTimeout: 재시도 소진 후 연결 실패.
        """
        rpc_payload = _rpc_envelope(text, context_id, message_id=message_id)

        for attempt in range(self._connect_retries + 1):
            try:
                async with self._http.stream(
                    "POST",
                    self.a2a_url,
                    json=rpc_payload,
                    headers={"Accept": "text/event-stream"},
                ) as response:
                    if response.status_code != 200:
                        if (
                            response.status_code >= 500
                            and attempt < self._connect_retries
                        ):
                            detail = (await response.aread())[:200]
                            logger.warning(
                                "upstream %d (attempt %d/%d): %s",
                                response.status_code,
                                attempt + 1,
                                self._connect_retries + 1,
                                detail,
                            )
                            await anyio.sleep(_backoff_s(attempt))
                            continue
                        detail_bytes = await response.aread()
                        raise UpstreamHTTPError(
                            response.status_code,
                            detail_bytes.decode("utf-8", errors="replace")[:500],
                        )
                    async for line in aiter_lines_with_keepalive(
                        response, keepalive_s=self._sse_keepalive_s,
                    ):
                        yield line
                    return
            except (httpx.ConnectError, httpx.ConnectTimeout):
                if attempt < self._connect_retries:
                    logger.warning(
                        "upstream connect failed (attempt %d/%d) — retrying",
                        attempt + 1, self._connect_retries + 1,
                    )
                    await anyio.sleep(_backoff_s(attempt))
                    continue
                raise


def _rpc_envelope(
    text: str,
    context_id: str,
    *,
    message_id: str | None = None,
) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": f"ug-{uuid.uuid4()}",
        "method": "SendStreamingMessage",
        "params": {
            "message": {
                "messageId": message_id or f"ug-msg-{uuid.uuid4()}",
                "role": "ROLE_USER",
                "parts": [{"text": text}],
                "contextId": context_id,
            },
        },
    }


def _backoff_s(attempt: int) -> float:
    """지수 backoff. 0.5s · 1s · 2s ..."""
    return 0.5 * (2 ** attempt)


class ChatProtocolUpstream:
    """Primary 의 chat protocol endpoint forward (#75 PR 4).

    - `POST /chat/send` — UG `/api/chat` 호출 시 forward (202 ack 그대로).
    - `GET /chat/stream?session_id=X` — UG `/api/stream` 영속 SSE 중계.

    A2A 와 분리된 chat tier 통로. Primary 가 chat session 별 큐 + 영속 SSE
    를 자체 관리하므로 UG 는 thin proxy.
    """

    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        send_url: str,
        stream_url: str,
        connect_retries: int,
        sse_keepalive_s: float,
    ) -> None:
        self._http = http
        self.send_url = send_url
        self.stream_url = stream_url
        self._connect_retries = connect_retries
        self._sse_keepalive_s = sse_keepalive_s

    async def chat_send(
        self,
        session_id: str,
        text: str,
        message_id: str | None = None,
        prev_chat_id: str | None = None,
    ) -> dict[str, Any]:
        """`POST /chat/send` forward. 응답 (202 ack) JSON 반환.

        `prev_chat_id` 는 user_chat_id — agent 가 자기 응답의 prev_chat_id 로
        사용 (chats chain, #75 PR 4).
        """
        body: dict[str, Any] = {"session_id": session_id, "text": text}
        if message_id:
            body["message_id"] = message_id
        if prev_chat_id:
            body["prev_chat_id"] = prev_chat_id
        for attempt in range(self._connect_retries + 1):
            try:
                r = await self._http.post(self.send_url, json=body)
                if r.status_code >= 500 and attempt < self._connect_retries:
                    logger.warning(
                        "chat_send upstream %d (attempt %d/%d)",
                        r.status_code, attempt + 1, self._connect_retries + 1,
                    )
                    await anyio.sleep(_backoff_s(attempt))
                    continue
                if r.status_code >= 400:
                    raise UpstreamHTTPError(r.status_code, r.text[:500])
                return r.json()
            except (httpx.ConnectError, httpx.ConnectTimeout):
                if attempt < self._connect_retries:
                    logger.warning(
                        "chat_send connect failed (attempt %d/%d) — retrying",
                        attempt + 1, self._connect_retries + 1,
                    )
                    await anyio.sleep(_backoff_s(attempt))
                    continue
                raise
        raise RuntimeError("chat_send unreachable")

    async def chat_stream(self, session_id: str) -> AsyncIterator[str | object]:
        """`GET /chat/stream?session_id=X` forward. SSE line + keepalive sentinel yield."""
        for attempt in range(self._connect_retries + 1):
            try:
                async with self._http.stream(
                    "GET",
                    self.stream_url,
                    params={"session_id": session_id},
                    headers={"Accept": "text/event-stream"},
                ) as response:
                    if response.status_code != 200:
                        if (
                            response.status_code >= 500
                            and attempt < self._connect_retries
                        ):
                            detail = (await response.aread())[:200]
                            logger.warning(
                                "chat_stream upstream %d (attempt %d/%d): %s",
                                response.status_code,
                                attempt + 1,
                                self._connect_retries + 1,
                                detail,
                            )
                            await anyio.sleep(_backoff_s(attempt))
                            continue
                        detail_bytes = await response.aread()
                        raise UpstreamHTTPError(
                            response.status_code,
                            detail_bytes.decode("utf-8", errors="replace")[:500],
                        )
                    async for line in aiter_lines_with_keepalive(
                        response, keepalive_s=self._sse_keepalive_s,
                    ):
                        yield line
                    return
            except (httpx.ConnectError, httpx.ConnectTimeout):
                if attempt < self._connect_retries:
                    logger.warning(
                        "chat_stream connect failed (attempt %d/%d) — retrying",
                        attempt + 1, self._connect_retries + 1,
                    )
                    await anyio.sleep(_backoff_s(attempt))
                    continue
                raise


__all__ = ["A2AUpstream", "ChatProtocolUpstream", "UpstreamHTTPError"]
