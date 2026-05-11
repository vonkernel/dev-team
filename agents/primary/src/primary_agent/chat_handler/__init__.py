"""Primary 의 chat protocol handler 패키지 (#75 PR 4).

UG↔P chat tier 통신의 server 측. wire schemas / SSE serialization 은
`dev_team_shared.chat_protocol` 사용.

서브모듈:
- `session` — SessionRuntime / SessionRegistry (per-session 상태 + in-memory registry)
- `router` — FastAPI router 조립 (`make_chat_router()`)
- `worker` — graph 호출 + chunks push (background task)

Lazy session: 미등록 session_id 가 도착하면 그 시점에 `SessionRuntime` 등록.
UG 가 사전에 `POST /api/sessions` 로 session row 를 만들지만 Primary 는
그 fact 를 모르고 lazy 생성 — LangGraph thread_id (= session_id) 만 매핑하면
충분 (graph 의 checkpointer 가 thread 별 history 관리).

Concurrency 모델 (per session):
- `outgoing_*` MemoryObjectStream 한 쌍 — POST 가 send, GET 이 receive.
- `lock` — 한 session 에 한 번에 graph 호출 1개 (sequential). 두 번째 POST 는
  lock 대기 → 큐 효과.

Subscriber 1 명 가정 (FE 한 탭). 다중 subscriber (multi-tab) 필요해지면
broadcast 패턴 도입 (v2).
"""

from primary_agent.chat_handler.router import make_chat_router
from primary_agent.chat_handler.session import SessionRegistry, SessionRuntime

__all__ = [
    "SessionRegistry",
    "SessionRuntime",
    "make_chat_router",
]
