# `dev_team_shared.a2a.server` — 모듈 가이드

`shared/a2a/server` 패키지는 **모든 에이전트가 공유하는 A2A 서버 추상화**.
각 에이전트는 본 패키지의 `make_a2a_router` 위에서 라우터를 조립하고
`MethodHandler` 구현체들을 등록만 하면 된다.

설계 정책 / SSE 자원 관리 / 중단 시나리오 등 "왜" 에 해당하는 내용은
[`docs/sse-connection.md`](../../../../../docs/sse-connection.md) 참조.
본 문서는 "어떻게" — 모듈 지도 / 공개 인터페이스 / 확장 방법 / 환경변수.

---

## 1. 모듈 지도

| 파일 | 책임 |
|---|---|
| `handler.py` | `MethodHandler` ABC — JSON-RPC 메서드 1개를 처리하는 단위 |
| `router.py` | `make_a2a_router(assistant_id, handlers)` — `/healthz` · `/.well-known/agent-card.json` · `/a2a/{aid}` 마운트 |
| `sse.py` | `sse_pack` · `sse_response` · `KEEPALIVE_SENTINEL` · `aiter_with_keepalive` |
| `graph_handlers/` | LangGraph 기반 기본 구현 sub-package — 아래 §2 참조 |
| `__init__.py` | 외부 노출 심볼 |

### 1.1. `graph_handlers/` 서브모듈

| 파일 | 책임 |
|---|---|
| `config.py` | env 기반 자원 관리 튜닝 (timeout / keepalive) |
| `session.py` | `ChatContext` + `log_session` (lifecycle 로깅) |
| `parse.py` | 요청 파싱 / LLM 응답 텍스트 추출 |
| `factories.py` | A2A Task / 이벤트 모델 조립 + 에러 텍스트 |
| `envelope.py` | JSON-RPC / SSE envelope 직렬화 |
| `stream.py` | `graph.astream` → SSE 라인 번역 (S1 polling · S2 keepalive) |
| `send_message.py` | `GraphSendMessageHandler` (단방향) |
| `send_streaming.py` | `GraphSendStreamingMessageHandler` (SSE) |
| `__init__.py` | 두 Handler 클래스만 외부 노출 |

---

## 2. 공개 인터페이스

```python
from dev_team_shared.a2a.server import (
    MethodHandler,           # ABC — 새 A2A 메서드 핸들러 작성 시 상속
    make_a2a_router,         # FastAPI APIRouter factory
    KEEPALIVE_SENTINEL,      # idle 시 yield 되는 sentinel
    aiter_with_keepalive,    # async iter wrapper (non-cancelling peek)
    sse_pack,                # dict → "data: ...\n\n" 직렬화
    sse_response,            # SSE StreamingResponse 표준 헤더
)

# 기본 구현 (LangGraph 그래프 컨슈머)
from dev_team_shared.a2a.server.graph_handlers import (
    GraphSendMessageHandler,
    GraphSendStreamingMessageHandler,
)
```

### 2.1. `MethodHandler` 계약

```python
class MyMethodHandler(MethodHandler):
    method_name: ClassVar[str] = "MyMethod"   # 등록 key

    async def handle(
        self,
        request: Request,
        rpc_id: Any,
        params: dict[str, Any],
    ) -> Response:
        # JSONResponse (단방향) 또는 StreamingResponse (SSE) 반환
        ...
```

런타임 자원 (graph / agent_card 등) 은 `request.app.state.<name>` 에서 lookup.
이 규약 덕분에 핸들러 인스턴스가 stateless 라 모든 요청에서 공유 가능.

### 2.2. `make_a2a_router` 사용 예

```python
app = FastAPI(lifespan=lifespan)
app.include_router(
    make_a2a_router(
        assistant_id="primary",
        handlers=[
            GraphSendMessageHandler(),
            GraphSendStreamingMessageHandler(),
        ],
    ),
)
```

라우터가 노출하는 경로:

| 경로 | 메서드 | 내용 |
|---|---|---|
| `/healthz` | GET | liveness |
| `/.well-known/agent-card.json` | GET | `request.app.state.agent_card` 직렬화 |
| `/a2a/{assistant_id}` | POST | JSON-RPC 2.0. 등록된 `MethodHandler` 들에 디스패치 |

규약: `app.state.agent_card` 는 lifespan 에서 세팅되어 있어야 함
(`shared.a2a.build_agent_card(config)` 결과).

### 2.3. `aiter_with_keepalive` 사용 예

```python
async for item in aiter_with_keepalive(graph.astream(...), keepalive_s=15):
    if item is KEEPALIVE_SENTINEL:
        yield ":keepalive\n\n"          # 프록시 idle timeout 방어용 comment
        continue
    # 통상 chunk 처리
    yield sse_pack({...})
```

**non-cancelling peek 패턴** — `asyncio.wait(timeout=...)` 로 `__anext__`
를 *기다리되 cancel 하지 않고* peek. timeout 시 sentinel 만 방출하고 같은
pending task 를 다음 라운드에서 계속 await. LangGraph `astream` 같은 비복원형
generator 에서도 chunk 유실 없이 동작.

---

## 3. 확장 방법

### 3.1. 새 A2A 메서드 추가

예: `GetTask` 메서드 지원하기.

```python
# 1) MethodHandler 구현체 작성
class GetTaskHandler(MethodHandler):
    method_name: ClassVar[str] = "GetTask"

    async def handle(self, request, rpc_id, params):
        task_id = params.get("taskId")
        # ... 그래프 / 체크포인터에서 task 상태 조회 ...
        return JSONResponse(rpc_result_response(rpc_id, task_dict))

# 2) 등록
app.include_router(
    make_a2a_router(
        assistant_id="primary",
        handlers=[
            GraphSendMessageHandler(),
            GraphSendStreamingMessageHandler(),
            GetTaskHandler(),                   # ← 한 줄 추가
        ],
    ),
)
```

기존 router / 다른 handler 코드는 **수정 불필요** (OCP 준수).
중복된 `method_name` 등록 시 `make_a2a_router` 가 `ValueError` 로 조기 차단.

### 3.2. 새 에이전트 추가

Architect / Librarian / Engineer / QA 모두 동일한 패턴:

```python
# agents/architect/src/architect_agent/server.py
app = FastAPI(lifespan=lifespan)
app.include_router(
    make_a2a_router(
        assistant_id="architect",
        handlers=[
            GraphSendMessageHandler(),
            GraphSendStreamingMessageHandler(),
        ],
    ),
)
```

`shared/a2a/server` 의 자원 관리 / 하드닝 (#23) 이 자동 적용. 에이전트별 추가
처리 (UG 중계, 인증 등) 는 해당 모듈에서 별도.

### 3.3. 다른 엔진 / transport 어댑터 작성

`GraphSendMessageHandler` 처럼 LangGraph 가 아닌 다른 엔진 (예: 자체 워크플로우
엔진, gRPC backend) 을 쓰고 싶으면 `MethodHandler` 를 직접 상속해 새 구현체를
만들면 된다. shared 에 동일 인터페이스로 추가하면 다른 에이전트도 재사용 가능.

---

## 4. 환경변수 카탈로그

`graph_handlers` 가 사용하는 env (override 가능):

| 변수 | 기본 | 의미 |
|---|---|---|
| `A2A_AGENT_TOTAL_TIMEOUT_S` | `600` | `graph.ainvoke` / `astream` 전체 수명 상한. 초과 시 `TASK_STATE_FAILED` |
| `A2A_SSE_KEEPALIVE_S` | `15` | SSE idle 시 `:keepalive` comment 발송 간격. 프록시/LB idle timeout 방어 |

---

## 5. 자원 관리 / SSE 하드닝 (요약)

자세한 건 [`docs/sse-connection.md`](../../../../../docs/sse-connection.md).
요지만:

- **S1** 매 chunk 시점 + Starlette `CancelledError` 양쪽으로 client disconnect 감지 → cascade cancel
- **S2** `aiter_with_keepalive` 가 idle 시 sentinel 방출 → 핸들러가 `:keepalive` 발송
- **S3** session lifecycle 구조화 로깅 (start / cancel / end + duration_ms / chunks / reason)
- **S4** `anyio.fail_after(_AGENT_TOTAL_TIMEOUT_S)` 로 graph 호출 전체 timeout

---

## 6. 관련 문서

- [`docs/sse-connection.md`](../../../../../docs/sse-connection.md) — 정책 / 시나리오 / #23 스코프
- [`docs/agent-runtime.md`](../../../../../docs/agent-runtime.md) — 에이전트 런타임 / Dockerfile 규약
- [`shared/src/dev_team_shared/a2a/README.md`](../README.md) — A2A 타입 / AgentCard
- [`agents/primary/README.md`](../../../../../agents/primary/README.md) — Primary 에이전트 (consumer 예시)
- [`user-gateway/docs/sse.md`](../../../../../user-gateway/docs/sse.md) — UG 고유 SSE 사항
