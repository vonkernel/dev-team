# A2A 메시징 / Task — 코드 진입 가이드

본 문서는 `shared/a2a` 코드를 처음 마주한 사람이 **A2A 프로토콜의 핵심 개념** 과
**우리 구현의 어디에 그게 들어가 있는지** 의 연결고리만 잡도록 짠 노트다.

A2A 스펙 전체 가이드가 아니다. 더 깊이가 필요하면
[A2A Protocol v1.0 spec](https://a2a-protocol.org/latest/specification/) 원문을
참조한다. 본 문서는 spec 의 한 단락과 우리 코드의 한 파일을 짝지어 보여주는
정도다.

> ⚠️ **본 프로토콜은 에이전트 간 통신 한정.** 사용자 ↔ Primary / Architect 의
> chat 통신은 A2A 가 아닌 별도 chat protocol (REST POST + 영속 SSE per session) —
> [`docs/proposal/architecture-chat-protocol.md`](../../../../../docs/proposal/architecture-chat-protocol.md) 참조.
> 사용자 ↔ 에이전트는 에이전트 간 통신과 다른 영역이라 자체 어휘 (Session /
> Chat / Assignment) 로 별도 정의했다 (#75).

---

## 1. 본 문서의 위치

`shared/a2a` 패키지에는 두 축의 문서가 있다:

| 문서 | 다루는 영역 |
|---|---|
| [`README.md`](./README.md) | **디스커버리 / 정체성** — AgentCard, `/.well-known/agent-card.json`, Config → 빌더 패턴 |
| **`messaging.md`** (본 문서) | **런타임 통신** — Message, Task, RPC 메서드, TaskState lifecycle |

전자가 "이 에이전트가 누구이고 뭘 할 수 있는지" 를 다루고, 후자가 "그 에이전트와 실제로 어떻게 대화하는지" 를 다룬다.

---

## 2. 핵심 어휘 — `Message` / `Task` / `contextId`

A2A 의 통신 계층은 세 가지 객체로 굴러간다:

**`Message`** — 한 발화의 단위 (입력).
사용자/에이전트가 보내는 한 마디로, `parts[]` 안에 텍스트(`Part.text`) 가 담긴다.
optional `taskId` 필드로 어느 Task 의 history 에 속하는지 명시 가능.
spec §6.4. 우리 코드: `types.py:Message`, `types.py:Part`, `types.py:Role` (`ROLE_USER` / `ROLE_AGENT`).

**`Task`** — 그 메시지를 처리하는 **서버 측 작업 단위 + 상태**.
ID 가 부여되고, `state` 가 lifecycle 을 따라 변하며 (§4 참조), `history[]` 에 받은 메시지와 응답이 누적된다. spec §6.2. 우리 코드: `events.py:Task`, `events.py:TaskStatus`.

> 비유: Message 가 손님의 **주문서**, Task 가 주방의 **작업 티켓**. 주문서는 한 장 받고 끝, 티켓은 "접수 → 조리 → 완료" 처럼 상태가 변한다.

### Message 와 Task 의 관계 — 응답 형식 alternative

A2A 공식 가이드 (https://discuss.google.dev/t/a2a-protocol-demystifying-tasks-vs-messages/255879):

- **Messages for Trivial Interactions** — 짧은 Q&A / discovery / clarification / pre-commitment negotiation. Task 미생성, Message 만 주고받음.
- **Tasks for Stateful Interactions** — long-running / 여러 step / 추적 필요. agent 가 "이 의도는 추적 가치 있다" 판단되면 Task 객체로 응답.
- 즉 **응답 형식의 alternative** — 첫 응답은 Message 또는 Task 둘 중 하나.

Task 가 commit 된 후엔 **그 Task 와 관련된 후속 Message 들이 Task 에 속함**:
- Message 의 `taskId` 필드로 backlink ("Notice how the `task_id` field in the Message object clearly indicates which task the user is referring to")
- Task 의 `history[]` 필드에 누적

**우리 도메인 Task = Assignment** (이름 변경 — #75). A2A Task 와 다른 객체:
- Assignment = 도메인 work item (open → done)
- A2A Task = wire-level 한 호출의 진행 추적 (SUBMITTED → COMPLETED)
- 한 Assignment 는 1 개 이상의 A2A Task 로 구성 가능 (위임 다회).

⚠️ **자동 Task wrap 은 A2A 스펙 요구사항 아님**. 현재 `graph_handlers/send_message.py` /
`send_streaming.py` 가 모든 SendMessage 응답을 Task 로 감싸고 있으나 이는 단순화일 뿐.
trivial 응답은 Message 만, stateful 만 Task — 후속 작업으로 분기 (#75).

---

### `contextId` — 에이전트 boundary 의 대화 namespace

**`contextId`** — **한 에이전트 boundary 안의** 다중 turn 대화 묶음.
같은 `contextId` 를 공유하는 여러 Task = 한 대화. 우리 구현은 이를 **LangGraph 의 `thread_id` 로 매핑** 해 체크포인터(Postgres) 가 대화별 state 를 영속화한다 — `graph_handlers/send_message.py` 의 `graph.ainvoke(..., config={"configurable": {"thread_id": ctx.context_id}})` 부분.

⚠️ `contextId` 는 **에이전트 쌍 사이의 conversation 식별자**이지 시스템 전체 trace 식별자가 아니다. Primary ↔ Engineer 의 contextId 와 Primary ↔ QA 의 contextId 는 다른 값이어야 한다 (각각 다른 두 당사자의 대화). 시스템 전체를 묶어 추적하려면 **`traceId`** (§5.x) 를 쓴다.

> ※ 사용자 ↔ Primary / Architect 의 chat 통신은 A2A 가 아니므로 contextId 가 아닌 **session_id** (chat protocol 의 식별자) 를 사용한다. A2A Context 가 chat session 에서 비롯되는 경우 (예: Primary 가 사용자 chat 중 Architect 에게 위임) 새 contextId 를 만들고, Doc Store 의 `a2a_contexts.parent_session_id` 로 source session 을 backlink ([knowledge-model](../../../../../docs/proposal/knowledge-model.md) §4.2).

---

## 3. 세 가지 동사 — RPC 메서드

A2A 가 정의하는 메서드 중 우리가 다루는 셋. 모두 JSON-RPC 2.0 의 `method` 필드 값이다.

### 3.1. `SendMessage` — 동기 요청-응답 (spec §9.4.1)

응답 받을 때까지 한 connection 을 유지하고 `Task` 한 덩어리를 받는다.

```mermaid
sequenceDiagram
    Client->>Agent: SendMessage(message)
    Note over Agent: graph.ainvoke(...)
    Agent-->>Client: Task(state=COMPLETED, history=[...])
```

본 구현은 `graph_handlers/send_message.py:GraphSendMessageHandler`. 핸들러 본문은 *parse → ChatContext.create → graph.ainvoke (`anyio.fail_after` 로 S4 timeout 적용) → make_completed_task / make_failed_task* 의 얇은 오케스트레이터.

### 3.2. `SendStreamingMessage` — SSE 스트림 (spec §9.4.2)

같은 일을 하지만 **응답을 조각조각** 받는다. 한 connection 위에서 이벤트 시퀀스가 흐른다:

```
Task(SUBMITTED) → ArtifactUpdate × N → StatusUpdate(COMPLETED|FAILED, final=true)
```

본 구현은 `graph_handlers/send_streaming.py:GraphSendStreamingMessageHandler`. LLM 토큰 chunk → `TaskArtifactUpdateEvent` 변환은 `graph_handlers/stream.py:stream_artifact_events` 가 담당하며, 같은 함수가 client disconnect 폴링(S1) / keepalive sentinel 처리(S2) 도 겸한다 (자세한 SSE 자원 관리는 [`docs/sse-connection.md`](../../../../../docs/sse-connection.md) 참조).

### 3.3. `GetTask` — 상태 조회 (spec §9.4.3)

이전에 시작한 Task 를 ID 로 조회하는 한 컷 snapshot.

```mermaid
sequenceDiagram
    Client->>Agent: SendStreamingMessage(...)
    Agent-->>Client: Task(id=abc, SUBMITTED)
    Note over Client: (연결 끊김)
    Client->>Agent: GetTask(taskId=abc)
    Agent-->>Client: Task(id=abc, COMPLETED, history=[...])
```

본 구현은 `client.py` 의 `A2AClient.get_task` (호출자 쪽) 만 있고 **서버 핸들러는 미구현**. 향후 `MethodHandler` 구현체 1개 추가 + `server.py` 의 list 에 등록만 하면 된다 (OCP — 다른 코드 변경 0줄).

### 비교

| | 시작 | 진행 관찰 | 사후 조회 |
|---|:---:|:---:|:---:|
| `SendMessage` | ✅ | ❌ | ❌ |
| `SendStreamingMessage` | ✅ | ✅ (SSE) | ❌ |
| `GetTask` | ❌ | ❌ | ✅ |

`SendMessage` / `SendStreamingMessage` 는 **새 Task 를 만드는** 동사 (둘 중 하나 선택), `GetTask` 는 **기존 Task 를 들여다보는** 동사.

---

## 4. TaskState — Task 의 lifecycle

`Task.status.state` 가 거치는 상태 머신. spec §6.3 + 우리 코드 `types.py:TaskState`.

### 4.1. State 카탈로그

| Enum | spec | 의미 | terminal? |
|---|---|---|:---:|
| `UNSPECIFIED` | `TASK_STATE_UNSPECIFIED` | protobuf zero-value placeholder. 런타임 상태 아님 | – |
| `SUBMITTED` | `submitted` | 접수 완료, 처리 미시작 | |
| `WORKING` | `working` | 활발히 처리 중 | |
| `INPUT_REQUIRED` | `input-required` | 추가 입력 대기 (사용자에게 질문) | |
| `AUTH_REQUIRED` | `auth-required` | 인증·인가 대기 | |
| `COMPLETED` | `completed` | 정상 완료 | ✅ |
| `FAILED` | `failed` | 오류로 종료 | ✅ |
| `CANCELED` | `canceled` | 취소됨 | ✅ |
| `REJECTED` | `rejected` | 처리 시작 전 거절 (정책 위반 / 능력 부족) | ✅ |

### 4.2. 전이 다이어그램

```mermaid
stateDiagram-v2
    state "input-required" as input_required
    state "auth-required" as auth_required

    [*] --> submitted

    submitted --> working : Accept
    submitted --> rejected : Policy Violation / Lack of Capability

    working --> auth_required : Credentials Needed
    auth_required --> working : Auth Success
    auth_required --> failed : Auth Denied / Timeout

    working --> input_required : Need More Info
    input_required --> working : Info Provided

    working --> completed : Success
    working --> failed : Runtime Error

    working --> canceled : Manual Abort
    submitted --> canceled
    auth_required --> canceled
    input_required --> canceled

    rejected --> [*]
    completed --> [*]
    failed --> [*]
    canceled --> [*]
```

핵심 불변식:

- 진입은 `submitted` 단 하나.
- `rejected` 는 `submitted` 에서만 도달 — 처리 *전* 거절 의미를 보존.
- terminal 4개: `rejected` / `completed` / `failed` / `canceled`. 같은 Task 재시작 불가.
- pause/resume 쌍: `working ↔ input-required`, `working ↔ auth-required`.

### 4.3. 본 구현의 정책 결정 (spec 미정의 영역)

- **`auth-required → failed`**: 인증 거부 / 타임아웃은 `failed` 로 처리. spec 은 미정의이지만 "외부 입력으로 회복 불가능한 비정상 종료" 라 `failed` 의 의미와 부합.
- **`input-required → failed` 부재**: 본 구현은 `input-required` 를 무기한 대기로 둔다. 사용자 응답 시간이 가변적이라 일률적 timeout 부적절. 영구 점유가 문제면 운영 도구로 stale Task 일괄 cancel 정책이 적합 (별도 이슈).
- **`submitted → canceled` 허용**: agent 가 working 으로 옮기기 전 사전 cancel 가능.

### 4.4. 현재 코드가 emit 하는 state

| 모듈 | emit 하는 state |
|---|---|
| `graph_handlers/factories.py` | `SUBMITTED` (initial) / `COMPLETED` / `FAILED` |
| `graph_handlers/send_streaming.py` | 위 + `TaskStatusUpdateEvent.final=true` 로 스트림 종결 |

`INPUT_REQUIRED` / `AUTH_REQUIRED` / `CANCELED` / `REJECTED` 는 enum 에 정의되어 있으나 아직 어떤 핸들러도 emit 하지 않는다. 추가 메서드 / 분기 도입 시 §4.2 전이 표를 따른다.

---

## 5. 호출 단위 = Task 단위

A2A spec 의 불변식: **`SendMessage` / `SendStreamingMessage` 한 호출 = `Task` 0 또는 1개**. spec §9.4 가 응답을 `Task` 또는 `Message` 중 하나로 한정.

| 응답 타입 | Task 개수 |
|---|:---:|
| `Task` | 1 |
| `Message` (즉답, lifecycle 추적 불필요) | 0 |

본 구현은 **현재 항상 `Task` 를 반환** — `Message`-only 응답 경로 미사용 (`graph_handlers/factories.py` 가 `make_*_task` 만 만든다). 이는 단순화이지 스펙 요구사항 아님 — trivial / stateful 분기는 후속 작업 (#75).

### 위임은 별도 호출 → 트리

Primary / Architect 가 다른 에이전트에게 일을 넘기는 건 **새로운 A2A 호출** 이고 그 호출은 그 호출대로 **자기 Task + 자기 contextId** 를 가진다:

```mermaid
sequenceDiagram
    Note over Primary: 사용자와 chat 중<br/>(chat protocol, A2A 아님)<br/>session_id=S
    Primary->>Engineer: SendMessage(contextId=Y)<br/>X-A2A-Trace-Id: T
    Note over Engineer: Task_B (contextId=Y)
    Engineer-->>Primary: Task_B(COMPLETED)
    Primary->>Architect: SendMessage(contextId=Z)<br/>X-A2A-Trace-Id: T (forward)
    Note over Architect: Task_C (contextId=Z, 별개 대화)
    Architect-->>Primary: Task_C(COMPLETED)
```

각 호출 경계에서 **1:1** 이고, 트리는 그 노드들이 모인 결과. `client.py:A2AClient` 가 위임 호출자 역할.

**핵심 — `contextId` 는 forward 하지 않는다**: Primary ↔ Engineer 의 `Y` 와 Primary ↔ Architect 의 `Z` 는 다른 값. 각 에이전트 boundary 가 자기 대화 namespace 를 가져 체크포인터 thread 가 격리된다. 시스템 전체 추적은 별도의 **`traceId`** 가 책임진다 (§5.x).

### 5.x. `traceId` — 시스템 전체 추적

`contextId` 가 boundary 안의 대화라면, `traceId` 는 boundary 를 **가로지르는** 추적 ID. 사용자가 UG chat 으로 시작한 한 의도가 Primary → Engineer → QA 까지 흐를 때 같은 traceId 가 따라다녀 **한 trace 로 묶여 로그 추적이 가능**.

규약 (`tracing.py:TRACE_ID_HEADER`):

| 항목 | 값 |
|---|---|
| Wire 위치 | HTTP 헤더 `X-A2A-Trace-Id` |
| 부재 시 | 서버 (`router.py`) 가 새 UUID 발급 → `request.state.trace_id` 에 보관 |
| 위임 시 forward | 위임자가 받은 traceId 를 `A2AClient.send_message(..., trace_id=...)` 인자로 그대로 forward |
| 로그 | `sse_session.start/cancel/end` 모든 로그에 `trace_id=...` 포함 (`session.py:log_session`) |

코드 매핑:

- 서버 수신 — `router.py` 가 헤더 읽음 → `request.state.trace_id` 보관
- 핸들러 — `ChatContext.create()` 가 자동으로 읽어 `ctx.trace_id` 에 저장
- 클라이언트 송신 — `A2AClient(trace_id=...)` (생성자 default) 또는 메서드 인자 `send_message(trace_id=...)` (per-call override)

추후 OpenTelemetry `traceparent` 헤더 도입 시 `tracing.py` 가 두 헤더를 모두 인식하도록 확장하면 된다.

### `contextId` 로 묶이는 다중 turn

같은 `contextId` 의 SendMessage 를 N 번 부르면 → Task 가 N 개 누적되며 같은 LangGraph thread 위에서 history 가 이어진다. "한 발화당 Task 1개" 가 누적되어 "한 대화" 를 이룬다 (단일 에이전트 boundary 안에서).

---

## 6. 부록

### 6.1. JSON 직렬화 규약 (spec §5.5)

- 필드명: **camelCase** (e.g., `messageId`, `contextId`)
- enum: **SCREAMING_SNAKE_CASE** 문자열 (e.g., `"TASK_STATE_COMPLETED"`)

본 구현은 Pydantic `model_dump(by_alias=True, exclude_none=True)` + `StrEnum` 으로 자동 처리. `graph_handlers/envelope.py:rpc_result` 가 한 곳에서 직렬화 옵션을 적용한다.

### 6.2. Method naming — pascal vs slash

A2A v1.0 (§9.4) 의 표기는 **PascalCase** (`SendMessage`, `SendStreamingMessage`, `GetTask`). 단, langgraph-api 초기 버전이 구(舊) 명세의 슬래시 표기 (`message/send` 등) 를 노출한 적이 있어, `client.py:_METHOD_MAP` 에서 두 스타일을 모두 지원한다 (기본값 = `pascal`).

### 6.3. 향후 확장

| 항목 | 도입 시 영향 |
|---|---|
| `CancelTask` 메서드 | `MethodHandler` 구현체 1개 추가 → `working`/`input-required`/`auth-required`/`submitted` → `canceled` 전이 활성화 |
| `ResubscribeTask` 메서드 | SSE 재구독으로 끊긴 스트리밍 복구 — 현 SSE 핸들러는 1회성이라 별도 핸들러 필요 |
| push notification | AgentCard `capabilities.pushNotifications=true` 와 연계, `input-required` / `auth-required` 진입 시 사용자에게 알림 |
| `input-required` timeout 정책 | §4.3 의 무기한 대기 정책 재검토 |

---

## 7. 관련 문서

- [`README.md`](./README.md) — 디스커버리 / AgentCard
- [`server/README.md`](./server/README.md) — A2A 서버 추상화 / `MethodHandler` 계약
- [`docs/sse-connection.md`](../../../../../docs/sse-connection.md) — SSE 자원 관리 정책 (#23)
- [A2A Protocol v1.0 spec](https://a2a-protocol.org/latest/specification/) — 공식 spec 원문
