# Chat Protocol — UG ↔ Primary / Architect

> #75 — A2A 와 chat 의 본질 mismatch 정리에서 도입.

사용자와 Primary / Architect 간 통신을 위한 별도 프로토콜. A2A 가 아님 (A2A 는
에이전트 간 task 위임 / 협상 — [messaging.md](../../shared/src/dev_team_shared/a2a/messaging.md)).

## 1. 왜 별도 프로토콜인가

A2A 의 본 의도 = task 위임 (Task lifecycle / Message / Context). 사용자 ↔ P/A
의 본 의도 = **자연스러운 논의** (chat). A2A 어휘 (Task `SUBMITTED → COMPLETED`)
를 chat 에 욱여넣은 게 schema / 운영 awkwardness 의 source — agent_tasks 의
fallback 만 채워짐 / agent_sessions 의 의미 모호 등 (#69 / #75).

→ Chat 은 chat 으로, A2A 위임은 A2A 로 분리. P/A 는 chat 중 합의된 작업을
**Assignment 로 발급** 하고, 그 실행만 다른 agent 에게 A2A 로 위임.

## 2. 어휘

| 객체 | 정의 |
|---|---|
| **Session** | 한 대화창 단위 (UG↔P/A). server-side 영속 (Doc Store `sessions` 테이블). 한 session = 한 agent_endpoint (`primary` / `architect`) |
| **Chat** | Session 안에서 주고받은 한 발화. server-side 영속 (Doc Store `chats` 테이블). `prev_chat_id` 로 시간순 chain |
| **Assignment** | Chat 중 합의된 도메인 work item. P/A 가 발급 (Doc Store `assignments`). 한 Assignment 안에서 여러 A2A Task 발생 가능 |

자세한 schema 는 [knowledge-model](knowledge-model.md) §4.2.

## 3. 통신 layer — Pattern A (영속 SSE per session)

### 흐름

```
세션 시작 시 1회:  UG → GET /api/stream?session_id=X     [SSE 쭉 열려 있음]
사용자 발화:       UG → POST /api/chat (text, session_id) → 202 ack
응답:              P/A → 위 SSE 채널로 chunk push
이후 사용자 발화:  POST 다시 (위 SSE 는 여전히 열려있음)
```

**이유**:
- POST 와 응답 channel 분리 → semantic 깔끔 (request != response stream)
- 영속 SSE 라 server-initiated push 미래 자연 (외부 이슈 변경 알림 같은 unprompted 이벤트)
- 큐 처리 자연 — POST 즉시 ack, 응답은 SSE 분리 도착
- 기존 SSE 인프라 (라우터 / keepalive / disconnect 폴링) 재사용

대안 (per-POST SSE) 은 multi-POST while busy 시 응답 분배 모호 — 채택 안 함.

### Endpoint 매트릭스

| Endpoint | 위치 | 호출자 | 책임 |
|---|---|---|---|
| `POST /api/chat` | UG | FE | 사용자 발화 제출. body: `{session_id, text}`. 응답: 202 + `{queued | processing}` |
| `GET /api/stream?session_id=X` | UG | FE | 영속 SSE 채널. 모든 응답 / queued ack / lifecycle 이벤트 receive |
| `GET /api/sessions` | UG | FE | 사이드바 chat list 조회 |
| `GET /api/history?session_id=X` | UG | FE | 새로고침 / 새 탭 시 chats hydrate |
| `POST /chat/send` (내부) | 각 agent (P / A) | UG | UG 가 forward |
| `GET /chat/stream?session_id=X` (내부) | 각 agent (P / A) | UG | UG 가 SSE 중계 |

### Routing

UG 가 session 의 `agent_endpoint` 컬럼 보고 해당 agent 의 internal endpoint
호출. 한 FE-facing SSE 가 한 agent-side SSE 와 1:1 매칭.

## 4. FE 측 영속 / 상태 관리

server `sessions` 테이블이 source of truth. FE 의 localStorage 는 사이드바
표시 / active session 빠른 전환을 위한 **cache 역할만**:

```
localStorage:
  activeSessionId   ← 현재 열려 있는 chat 의 session_id
  sessions          ← 사이드바 cache (id, title, agent_endpoint, last_chat_at)
```

페이지 로드 시:
1. localStorage 에서 `activeSessionId` 복원
2. `GET /api/sessions` 로 사이드바 list refresh
3. `GET /api/history?session_id=<active>` 로 활성 session 의 chats hydrate
4. `GET /api/stream?session_id=<active>` 로 영속 SSE 재연결

새 chat 버튼 → 새 session 생성 (`POST /api/sessions`) → 활성 전환.

## 5. 메시지 큐 — Primary 측 책임 (#72)

P/A 의 chat handler 가 thread-level 동시성 관리:

- **idle**: 즉시 graph 호출 → SSE 로 chunk
- **busy**: in-process 큐에 적재 → POST 응답 `queued` ack + SSE 로 `queued`
  이벤트 (FE 가 사용자 발화 버블에 "큐에 적재됨" 표시)
- 처리 끝나면 큐 drain → 누적 메시지 batch 로 단일 user message 합쳐 graph
  호출. Separator 로 timestamp 메타 포함:
  ```
  사용자 첫 발화

  [N초 뒤 추가 발화]
  사용자 둘째 발화
  ```

### 의미 판단은 main LLM 에 위임

오타 noise / 정정 / 보충 / 명시 cancel 의도 같은 **의미 판단은 P/A 의 main
LLM 이 persona 가이드** 로 처리. UG 는 인터페이스만, 의미 영역은 agent 책임
(SOLID / SRP — UG 가 LLM 가지지 않음).

persona 가이드 (예 — Primary):
> 사용자가 응답 도중 추가 발화한 메시지가 batch 로 들어올 수 있다.
> separator `[N초 뒤 추가 발화]` 가 보이면 다음과 같이 판단:
> - 의미 없는 오타 / 1~2 글자 noise → 무시하고 본 의도에 응답
> - 보충 / 정정 → 통합해서 응답
> - 명시 중단 의도 ("멈춰", "그만", "다시") → 진행 방향 재검토

자세한 정책 / 구현은 #72.

## 6. Cancel / Stop

### 자연어 cancel ("그만", "멈춰" 등)

- 큐에 적재되어 main LLM 까지 전달됨
- LLM 이 의미 판단해서 다음 turn 에서 사과 / 재시도
- 단점: 응답 chunk 이미 흘러간 후라 즉시 중단 못 함

### 명시 Stop (Stop 버튼)

- FE 의 명시 cancel UI — 영속 SSE 의 별 RPC 호출 (`POST /api/stop?session_id=X`)
- UG 가 agent 에게 cancel 신호 forward (예: WebSocket close 또는 명시 `POST /chat/cancel`)
- agent 는 graph 즉시 cancel + 큐 폐기

## 7. 영속 / Chronicler

UG 가 chat lifecycle 이벤트를 Valkey Streams 로 publish:

| 이벤트 | 트리거 |
|---|---|
| `chat.session.start` | 사용자가 새 chat session 시작 |
| `chat.append` | 사용자 / agent 의 발화 |
| `chat.session.end` | session 닫힘 (페이지 떠남 / 명시 종료 / TTL) |

Chronicler 가 consume 해 Doc Store `sessions` / `chats` 컬렉션에 영속화
([architecture-event-pipeline](architecture-event-pipeline.md)).

P/A 의 Assignment 발급은 별도 이벤트 (`assignment.create` / `assignment.update`).

## 8. A2A 와의 경계

| 항목 | Chat tier | A2A tier |
|---|---|---|
| 통신 주체 | 사용자 ↔ Primary / Architect | 에이전트 ↔ 에이전트 |
| Transport | REST POST + 영속 SSE per session | JSON-RPC 2.0 over HTTP, SSE for streaming |
| 식별자 | `session_id` (서버 발급 UUID) | `contextId` (A2A wire), `traceId` (트리 join) |
| 메시지 객체 | Chat (Doc Store `chats`) | A2A Message (Doc Store `a2a_messages`) |
| 작업 단위 | Assignment (Doc Store `assignments`) | A2A Task (Doc Store `a2a_tasks`) |
| Lifecycle | Session start/end + Chat append | A2A Context start/end + Task SUBMITTED→COMPLETED |
| Spec | 자체 정의 (본 문서) | [A2A v1.0](https://a2a-protocol.org/latest/specification/) |

A2A Context 가 chat session 에서 비롯되는 경우 `a2a_contexts.parent_session_id` /
`parent_assignment_id` 로 source 추적 ([knowledge-model](knowledge-model.md) §4.2).

## 9. 관련

- 본 프로토콜 도입 시발: #75 (UG↔P/A chat tier 분리 재설계)
- Doc Store schema: [knowledge-model](knowledge-model.md) §4.2
- A2A 프로토콜 (대비): [shared/a2a/messaging.md](../../shared/src/dev_team_shared/a2a/messaging.md)
- UG 측 책임: [architecture-user-gateway](architecture-user-gateway.md)
- Primary 큐 정책: #72
- FE multi-chat UI: #70
- Stop 버튼 / streaming flag: #71
