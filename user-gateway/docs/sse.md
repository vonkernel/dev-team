# SSE 연결 설계 노트 — User Gateway

본 문서는 UG 와 관련된 **SSE(Server-Sent Events) 기반 A2A 중계** 의 설계 맥락과
지금까지 검토한 자원 관리 / 예기치 못한 중단 대비 / UG 고유 계약 사항을 기록한다.

- 작성 배경: #6 / #7 구현 과정에서 공유된 고려 사항. 공용(shared) 계층 개선은
  **#23 이슈** 로 별도 관리, 본 문서는 **UG 레벨에서만 의미 있는 항목** 중심.
- 코드 위치 (SOLID 분리 — 모듈별 책임):
  - `user_gateway/main.py` — app 조립 (lifespan · 미들웨어 · 라우터 include)
  - `user_gateway/routes.py` — `/api/chat` 오케스트레이션 (SSE generator · lifecycle)
  - `user_gateway/upstream.py` — `A2AUpstream` (httpx → Primary, connect retry)
  - `user_gateway/translator.py` — A2A 이벤트 → UG ChatEvent 순수 함수
  - `user_gateway/sse.py` — `sse_pack` · `KEEPALIVE_SENTINEL` · line-iter
  - `user_gateway/middleware.py` — `CacheControlMiddleware`
  - `user_gateway/config.py` — env 기반 AppConfig
  - `user-gateway/frontend/src/api.ts` — fetch + ReadableStream SSE 파서

---

## 1. 현재 구조

```mermaid
flowchart LR
    B["Browser (React)"]
    subgraph UG["User Gateway (FastAPI)"]
        API["POST /api/chat<br/>A2A ↔ 단순 이벤트 번역"]
        Static["GET /*<br/>Vite 정적 자원"]
    end
    subgraph P["Primary Agent"]
        Graph["graph.astream<br/>체크포인트 · LLM 호출"]
    end
    Anthropic["Anthropic API"]

    B -->|GET /| Static
    B <-->|"POST fetch + SSE<br/>{meta|chunk|done|error}"| API
    API <-->|"httpx.stream + A2A SSE<br/>(SendStreamingMessage)"| Graph
    Graph <-->|HTTP| Anthropic
```

- **브라우저는 A2A 스펙을 직접 알 필요가 없다.** UG 가 A2A 이벤트
  (`task` / `artifact-update` / `status-update`) 를 UG 고유의 단순 이벤트
  (`meta` / `chunk` / `done` / `error`) 로 번역한다.
- 브라우저 ↔ UG 는 `POST + ReadableStream` (EventSource 는 GET 만 되어
  메시지 body 를 실을 수 없음).

---

## 2. 자원 관리 현황 (#7 머지 시점)

| 자원 | 정리 시점 | 상태 |
|---|---|---|
| UG 의 공용 `httpx.AsyncClient` | FastAPI lifespan finally → `aclose()`. Limits 명시 (env override) | ✅ |
| per-request upstream stream (`http.stream`) | `async with` context exit. connect error 재시도 포함 | ✅ |
| SSE session lifecycle | start / end 구조화 로그 (context_id / reason / duration_ms / chunks) | ✅ |
| Client disconnect 감지 | chunk 사이 + keepalive 타이머 시점에 `request.is_disconnected()` 폴링 → cascade cancel | ✅ (UG 측) |
| 프록시 idle timeout 방어 | `:keepalive\n\n` comment 주기 발송 (`UG_SSE_KEEPALIVE_S`) | ✅ (UG 측) |
| Primary 쪽 `graph.astream` iterator | cancel 전파 | ✅ (공용 측 보강은 #23) |
| 정적 자원 (`/`, `/assets/*`) | `StaticFiles` + `CacheControlMiddleware` 로 적절한 Cache-Control | ✅ |

## 3. 예기치 못한 연결 중단 — 전수 검토

| 시나리오 | 대응 | 상태 |
|---|---|---|
| 브라우저 탭 닫기 / 네트워크 단절 | Starlette write 시점 감지 + `request.is_disconnected()` 폴링으로 chunk 사이에도 조기 감지 → cascade cancel | ✅ 반영됨 (UG 측) |
| UG ↔ Primary TCP 장애 | `except httpx.HTTPError` → `{type:"error"}` + connect error 시 지수 backoff 재시도 | ✅ 반영됨 |
| Primary ↔ Anthropic 장애 | Primary 의 `except Exception` → `TASK_STATE_FAILED` → UG 가 error 이벤트로 전달 | ✅ |
| Primary / UG 프로세스 crash | 소켓 끊김 → fetch 예외 → FE 의 catch + retry 버튼 노출 | ✅ 반영됨 |
| LLM 무한 대기 | UG 의 `anyio.fail_after(UG_UPSTREAM_TOTAL_TIMEOUT_S)` 로 전체 스트림 수명 상한 (기본 300s) | ✅ 반영됨 (UG 측) |
| 프록시/LB idle timeout | `:keepalive\n\n` comment 주기 발송 (기본 15s). idle 구간에도 TCP 연결 유지 | ✅ 반영됨 (UG 측, `_aiter_lines_with_keepalive`) |
| Half-open TCP | OS/uvicorn 기본 socket keepalive 에 의존 | 🟩 Later |
| Slow client backpressure | Starlette 가 write 대기로 자연스러운 backpressure | 🟩 Later |

> 공용(agent) 측의 동일 대응은 **#23** 에서 별도 브랜치로 반영 예정 (본 문서는 UG 관점).

---

## 4. UG 에만 적용되는 조치 전수 목록

Agent 와 달리 UG 는 **브라우저 대면 + upstream 호출자** 역할이라 고유한 책임이 있음.
개선 항목을 영역별로 정리한다 (공용 계층에 이미 심을 항목은 별도 표기).

### 4.1. Upstream (UG → Primary) 통신 관리

| 항목 | 우선 | 상태 | 구현 |
|---|---|---|---|
| **Upstream 전체 스트림 timeout** (U1) | 🟥 Must | ✅ 반영됨 | `routes.chat` 의 `event_stream` 을 `anyio.fail_after(UG_UPSTREAM_TOTAL_TIMEOUT_S)` 로 감쌈. 기본 300s, 초과 시 `{type:"error",message:"upstream timeout after Ns"}` |
| **httpx.Limits 튜닝** (U2) | 🟨 Should | ✅ 반영됨 | `main.lifespan` 에서 `httpx.Limits(max_connections, max_keepalive_connections)` 명시. `UG_UPSTREAM_MAX_CONN` / `UG_UPSTREAM_MAX_KEEPALIVE` 환경변수 override |
| **Upstream retry / backoff** (U3) | 🟨 Should | ✅ 반영됨 | `A2AUpstream.stream_message` 가 connect error / 5xx 시 지수 backoff 로 `UG_UPSTREAM_CONNECT_RETRIES` 회 재시도 (기본 2). 스트리밍 중간 실패는 재시도 불가 (토큰 이미 방출) |
| **Upstream 요청 header 전파** | 🟩 Later | — | 인증 토큰 propagation. M3+ 인증 도입 시 |

### 4.2. 브라우저-facing 보호

| 항목 | 우선 | 상태 | 구현 |
|---|---|---|---|
| **CORS 정책** (U4) | 🟨 Should | ✅ 반영됨 | `main.py` 에서 `CORSMiddleware` + `UG_ALLOWED_ORIGINS` 환경변수 (콤마 구분 allowlist). 빈 값이면 같은 origin 만 |
| **Per-client rate limit** | 🟩 Later | — | slowloris / 남용 방어. 단일 사용자 환경엔 불필요 |
| **Request body size limit** | 🟩 Later | — | FastAPI 기본값 외 추가 |

### 4.3. 프로토콜 번역 계약

| 항목 | 우선 | 상태 | 구현 |
|---|---|---|---|
| **UG → FE 이벤트 포맷 문서화** (U5) | 🟨 Should | ✅ 반영됨 | 본 문서 §5 표 + FE `types.ts` 의 `ChatEvent` 타입. 필요 시 `code`/`retryable` 필드 추가 가능 |
| **A2A → FE 번역 테이블 공식화** (U6) | 🟨 Should | ✅ 반영됨 | 본 문서 §6 매핑 표. 코드 구현은 `translator.translate()` 순수 함수 |

### 4.4. FE 재시도 / 재연결 UX

| 항목 | 우선 | 상태 | 구현 |
|---|---|---|---|
| **FE 끊김 시 재시도 정책** (U7) | 🟨 Should | ✅ 반영됨 | 실패한 agent 버블에 "↻ 다시 시도" 버튼 (`MessageBubble`). 클릭 시 원본 유저 텍스트 (`ChatMessage.sourceText`) 로 `doSend` 재호출. 이전 실패 버블은 그대로 유지 |
| **Request idempotency** | 🟩 Later | — | FE 가 매 전송마다 새 `messageId` 생성. 서버측 dedup 까지는 불필요 |

### 4.5. 정적 자원 서빙

| 항목 | 우선 | 상태 | 구현 |
|---|---|---|---|
| **Cache-Control 헤더** (U8) | 🟨 Should | ✅ 반영됨 | `middleware.CacheControlMiddleware`: `/assets/*` → `public, max-age=31536000, immutable` (Vite hash 안전), `/` 및 `*.html` → `no-cache` |
| **gzip / brotli 압축** | 🟩 Later | — | 프록시 레이어에서 처리 권장 |
| **SPA fallback** | 🟩 Later | — | 단일 페이지라 불필요. 라우팅 도입 시 |

### 4.6. 인증 / 세션 (M3+)

| 항목 | 우선 | 비고 |
|---|---|---|
| Session token 발급 / 검증 | 🟩 Later | 현재 M2 는 no-auth |
| Token upstream A2A 전달 | 🟩 Later | Primary 가 user-id 식별할 때 필요 |

---

## 5. UG → FE 이벤트 포맷 계약

`POST /api/chat` 의 SSE 응답은 다음 타입의 JSON payload 를 `data:` 라인으로 전달한다.

| `type` | 언제 | 필드 | 의미 |
|---|---|---|---|
| `meta` | 세션 최초 1회 | `contextId: string` | FE 가 후속 요청에 `contextId` 를 이어붙여 thread 를 유지하도록 알림 |
| `chunk` | LLM 토큰 chunk 도착 시 N회 | `text: string` | 현재 agent 버블에 append 할 텍스트 조각 |
| `done` | 정상 완료 시 1회 | — | 스트림 종료. FE 는 버블의 `streaming` 상태 해제 |
| `error` | 실패 시 1회 (최종) | `message: string` | 오류 설명. 향후 `code`, `retryable` 필드 추가 가능 |

SSE 인코딩: `data: {json}\n\n`. 하트비트는 (개선 후) `:keepalive\n\n` comment 라인
— FE 는 comment 라인을 무시한다.

---

## 6. A2A → UG 이벤트 번역 테이블

UG 가 Primary 로부터 받는 A2A SSE 이벤트는 다음과 같이 번역된다:

| A2A 이벤트 | 조건 | UG 이벤트 |
|---|---|---|
| `Task{status.state=TASK_STATE_SUBMITTED}` | 최초 1회 | `meta{contextId}` (UG 가 만든 contextId 를 그대로 전달) |
| `TaskArtifactUpdateEvent{append=true, parts:[{text}]}` | N회 | `chunk{text}` |
| `TaskStatusUpdateEvent{status.state=TASK_STATE_COMPLETED, final=true}` | 종료 | `done` |
| `TaskStatusUpdateEvent{status.state=TASK_STATE_FAILED, final=true}` | 오류 | `error{message}` (status.message.parts[0].text 추출) |
| `TaskArtifactUpdateEvent` 의 `parts` 에 text 외 타입 (file, data 등) | 미래 | 현재는 skip. 확장 시 추가 타입 정의 필요 |

## 7. 의존 관계 / 구현 순서 힌트

- **#23 (공용 SSE 하드닝)** 이 먼저 들어가 있으면 UG 의 U1 timeout 실측이 깨끗함
  (Primary 쪽 keepalive / disconnect polling 이 이미 동작).
- 다만 독립 변경이라 병렬 진행 가능.

## 8. 검증 체크리스트 (UG 레벨)

개선 반영 후 다음을 수동 확인:

- `curl -sS --no-buffer -X POST http://localhost:8080/api/chat -d '{"text":"긴 질문..."}'` 중
  **Ctrl-C** → UG 로그에 `sse_session.cancel(reason=client_disconnect)` 기록
- idle 5초 초과 시 스트림에 `:keepalive` 라인 주기 관찰
- UG 의 upstream timeout (예: 5s 로 임시 설정) 을 초과하는 LLM 지연 유도 →
  `{type:"error", message:"upstream timeout"}` 이벤트 수신
- `curl -I http://localhost:8080/` → `Cache-Control: no-cache`, `/assets/<hash>.js` → `Cache-Control: immutable, max-age=31536000`
- FE 브라우저에서 서버 강제 종료 → 에러 버블 + retry 버튼 (U7 적용 후) 노출

---

## 9. 미해결 / 재검토 필요

- **LLM cancel cascade 완전성** — cascade 가 Anthropic API 요청까지 닿는지
  `langchain-anthropic` / httpx 구현 의존. 실측 결과를 #23 에 기록.
- **Graceful shutdown 시 진행 중 세션 drain 정책** — SIGTERM 수신 시 새 요청
  거부 + 진행 중 세션 완료 대기 vs 즉시 cancel 후 에러 이벤트 방출. M3+ 결정.
- **멀티 에이전트 시대의 UG 확장** — UG 가 Primary 외 다른 agent 로도 라우팅
  하게 될 때, `/api/chat?agent=architect` 같은 디스패치 필요. 현재 구조는
  Primary 하드코딩.
