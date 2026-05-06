"""Librarian 1차 통합 검증 스크립트.

서버: http://localhost:9002 (이미 부팅된 컨테이너 가정)
대상: A2A `SendStreamingMessage` 로 자연어 요청 → LLM 이 tool 호출 + 자연어 응답

검증 시나리오 (read-only — Doc Store 데이터 변경 X):
  1. AgentCard 정상
  2. "wiki_pages.list" 자연어 요청 → wiki_pages_list tool 호출 + 자연어 응답
  3. "agent_tasks 몇 개" → agent_tasks_list 호출 + count 응답
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid

import httpx


BASE = "http://localhost:9002"
A2A_URL = f"{BASE}/a2a/librarian"


async def fetch_agent_card() -> dict:
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{BASE}/.well-known/agent-card.json")
        r.raise_for_status()
        return r.json()


async def send_streaming_message(text: str) -> list[dict]:
    """A2A SendStreamingMessage 호출 → 모든 SSE 이벤트 수집."""
    payload = {
        "jsonrpc": "2.0",
        "id": f"verify-{uuid.uuid4()}",
        "method": "SendStreamingMessage",
        "params": {
            "message": {
                "messageId": f"msg-{uuid.uuid4()}",
                "role": "ROLE_USER",
                "parts": [{"text": text}],
                "contextId": str(uuid.uuid4()),
            },
        },
    }
    events: list[dict] = []
    async with httpx.AsyncClient(timeout=120.0) as c:
        async with c.stream(
            "POST", A2A_URL,
            json=payload,
            headers={"Accept": "text/event-stream"},
        ) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if line.startswith("data: "):
                    raw = line[len("data: "):].strip()
                    if not raw:
                        continue
                    try:
                        events.append(json.loads(raw))
                    except json.JSONDecodeError:
                        events.append({"raw": raw})
    return events


def _extract_final_text(events: list[dict]) -> str:
    """SSE events 에서 최종 자연어 응답 추출. artifact-update 이벤트의 parts.text 합침."""
    pieces: list[str] = []
    for e in events:
        result = e.get("result") or {}
        # streaming artifact chunk: result.artifact.parts[].text
        artifact = result.get("artifact") or {}
        for part in artifact.get("parts") or []:
            t = part.get("text")
            if t:
                pieces.append(t)
        # task status message (final): result.status.message.parts[].text
        status_msg = (result.get("status") or {}).get("message") or {}
        for part in status_msg.get("parts") or []:
            t = part.get("text")
            if t:
                pieces.append(t)
    return "".join(pieces)


async def main() -> int:
    print("[1] AgentCard fetch")
    card = await fetch_agent_card()
    assert card.get("name") == "librarian", f"unexpected name: {card.get('name')}"
    print(f"    name={card['name']}, streaming={card['capabilities']['streaming']}")

    print("\n[2] '위키 페이지 목록 알려줘' (read-only)")
    events = await send_streaming_message(
        "doc-store 의 wiki_pages 를 page_type 무관하게 list 해줘. limit=5 면 충분.",
    )
    print(f"    received {len(events)} SSE events")
    final = _extract_final_text(events)
    print(f"    final text (first 300):\n      {final[:300]!r}")
    if not final:
        print("    !! 자연어 응답 없음 — events:")
        for i, e in enumerate(events[:6]):
            print(f"      [{i}] {json.dumps(e, ensure_ascii=False)[:200]}")
        return 1

    print("\n[3] 'agent_tasks 몇 개?' (count via list)")
    events = await send_streaming_message(
        "agent_tasks collection 에 현재 몇 개의 task 가 있는지 list 도구로 확인하고 개수만 알려줘.",
    )
    final = _extract_final_text(events)
    print(f"    final text (first 300):\n      {final[:300]!r}")
    if not final:
        print("    !! 자연어 응답 없음")
        return 1

    print("\nALL PASS ✅")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
