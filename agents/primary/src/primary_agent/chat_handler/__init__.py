"""Primary 의 chat protocol handler 패키지 (#75 PR 4).

UG↔P chat tier 통신의 server 측. wire schemas / SSE serialization /
SessionRuntime · SessionRegistry 는 모두 `dev_team_shared.chat_protocol` —
본 패키지는 Primary 의 graph 호출 / FastAPI 라우터 조립만.

서브모듈:
- `router` — FastAPI router 조립 (`make_chat_router()`)
- `worker` — graph 호출 + ChatEvent push (background task)

Lazy session: 미등록 session_id 가 도착하면 그 시점에 shared `SessionRuntime`
등록. UG 가 사전에 `POST /api/sessions` 로 session row 를 만들지만 Primary 는
그 fact 를 모르고 lazy 생성 — LangGraph thread_id (= session_id) 만 매핑하면
충분 (graph 의 checkpointer 가 thread 별 history 관리).

Concurrency 모델 (per session):
- `SessionRuntime.send/receive` — message-aware in-memory 버퍼. send 가 절대
  block X (graph forward progress 보장), buffer overflow 시 oldest message 의
  chunks atomic drop.
- `SessionRuntime.lock` — 한 session 에 한 번에 graph 호출 1개 (sequential).
  두 번째 POST 는 lock 대기 → 큐 효과.

TTL evict (M3 가정):
- shared `SessionRegistry` 의 background sweeper 가 idle session evict.
- 진행 중 graph task 가 있으면 cancel — 마지막 완료 노드까지의 state 는
  LangGraph checkpoint 에 보존되므로 손실 X.

Subscriber 1 명 가정 (FE 한 탭). 다중 subscriber (multi-tab) 필요해지면
broadcast 패턴 도입 (v2).
"""

from dev_team_shared.chat_protocol import SessionRegistry, SessionRuntime

from primary_agent.chat_handler.router import make_chat_router

__all__ = [
    "SessionRegistry",
    "SessionRuntime",
    "make_chat_router",
]
