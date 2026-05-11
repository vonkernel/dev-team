# Chronicler (CHR) — AI 에이전트 작업 규칙

본 모듈을 수정하는 AI 에이전트 (Claude / 기타) 가 따라야 할 규약. root
`CLAUDE.md` 위에 본 모듈 한정 사항.

---

## 1. 정체성

- **에이전트가 아님.** LangGraph / LLM / Role Config / A2A 일체 미사용.
- 단일 Python 스크립트 (long-lived process). Valkey Stream consumer + Doc
  Store MCP 클라이언트 두 가지로만 구성.
- 책임: **chat / assignment / A2A 이벤트 수집 → Doc Store 영속화**.

자세한 시스템 위치 / 흐름은 [`docs/proposal/architecture-event-pipeline.md`](../docs/proposal/architecture-event-pipeline.md) 참조.

---

## 2. 데이터 흐름

```
publisher (UG / P / A / ...) → Valkey Stream "a2a-events" → CHR → Doc Store MCP
       (XADD)                  (Consumer Group "chronicler") (XREADGROUP / 처리 / XACK)
```

#75 재설계 후 이벤트는 **3 layer / 10 type**:

| Layer | Event types | publisher |
|---|---|---|
| **Chat** | `session.start` / `chat.append` | UG (user 발화) / agent (agent 발화) |
| **Assignment** | `assignment.create` / `assignment.update` | P/A (chat 중 합의 시점) |
| **A2A** | `a2a.context.start` / `a2a.context.end` / `a2a.message.append` / `a2a.task.create` / `a2a.task.status_update` / `a2a.task.artifact` | 각 에이전트 A2A handler |

> **session 은 종료 개념 없음** — `session.end` event 폐기 (PR 3, #75).
> archive 가 필요해지면 별 컬럼 (`archived_at`) 으로.

> **a2a_context 종료는 agent 결정** — `a2a.context.end` 는 agent 가 "이
> inter-agent 대화 마무리" 판단 시 발화 (RPC 단위 아님).

스키마는 `dev_team_shared.event_bus.events` (Pydantic). publisher 와 contract.

---

## 3. Idempotency / 재시작 내구성

- 이벤트마다 `event_id` (UUID) — publisher 가 부여
- CHR 가 처리 완료 후 `XACK` — 그 사이 죽으면 PEL 의 미처리 메시지 재전달
- **재시도 시 중복 처리 방지** (이중 적재 방어):
  - **publisher-supplied id 패턴** (PR 1/2): `sessions` / `assignments` / `a2a_contexts` / `a2a_tasks` 는 publisher 가 발급한 UUID 가 그대로 row id. 같은 event_id 가 재전달돼도 `<entity>_get(id)` 으로 existing 체크 → skip
  - **wire id dedup**: immutable collection (`chats` / `a2a_messages` / `a2a_task_status_updates` / `a2a_task_artifacts`) 은 `message_id` / `task_id` / `artifact_id` 등 wire id 가 unique key 역할
  - **double-end guard**: `A2AContextEndProcessor` 는 `ended_at` 이미 set 이면 skip — agent 가 잘못 발화해도 첫 close 시각 보존
- DB 트랜잭션 내 다중 쓰기는 본 모듈 책임 X — Doc Store MCP 가 단순 CRUD

---

## 4. 새 이벤트 type 추가 절차 (OCP)

새 이벤트 type 이 도입될 때:

1. `dev_team_shared.event_bus.events` 에 `_EventBase` 상속한 새 Pydantic 클래스 추가 + `event_type: Literal["..."]` default 지정
2. `chronicler/src/chronicler/processors/<name>.py` 작성 — `EventProcessor` 상속 + `event_type` ClassVar 지정 + `process()` 구현
3. `chronicler/src/chronicler/processors/__init__.py` 의 `ALL_PROCESSORS` 리스트에 인스턴스 1줄 추가

**`handler.py` / `consumer.py` 수정 0줄** 이 OCP 충족 시그널.

처리 dispatch 는 `EventHandler.registered_event_types` 로 동적 도출 (각
이벤트 클래스의 `event_type` Literal default 가 wire 키). consumer 도 그
매핑을 받아 parse → handle.

---

## 5. 절대 금지 사항

- **LangGraph / LLM 도입** — CHR 는 thin transformer. 추론 책임은 Librarian / 에이전트
- **Doc Store 직접 연결** — 반드시 MCP 경유 (`shared.mcp_client`)
- **Valkey 외 다른 broker 추가** — 본 마일스톤 범위 밖
- **immutable collections 의 update / 수정** (`chats` / `a2a_messages` /
  `a2a_task_status_updates` / `a2a_task_artifacts`)

---

## 6. 의존 / 운영

| 의존 | 용도 |
|---|---|
| `redis>=7.4.0` (asyncio) | Valkey Streams 클라이언트 |
| `mcp>=1.27.0` | streamable HTTP MCP client |
| `dev_team_shared.event_bus` | 이벤트 schema |
| `dev_team_shared.doc_store` | Doc Store MCP typed client |
| `dev_team_shared.mcp_client` | streamable HTTP MCP 클라이언트 wrapper |

env:
- `VALKEY_URL` — `redis://valkey:6379`
- `DOC_STORE_MCP_URL` — `http://doc-store-mcp:8000/mcp`
- `CHRONICLER_CONSUMER_GROUP` — 기본 `chronicler`
- `CHRONICLER_CONSUMER_NAME` — 기본 hostname (k8s 시 pod name)

---

## 7. 관련 문서

- root [`/CLAUDE.md`](../CLAUDE.md) — 프로젝트 일반 규약
- [`docs/proposal/architecture-event-pipeline.md`](../docs/proposal/architecture-event-pipeline.md) — Chronicler 정체성 / chat·assignment·A2A 3 layer 이벤트
- [`docs/proposal/knowledge-model.md`](../docs/proposal/knowledge-model.md) §4.2 — Doc Store schema (sessions / chats / assignments / a2a_*)
- [`mcp/doc-store/CLAUDE.md`](../mcp/doc-store/CLAUDE.md) — Doc Store MCP collection / 6 op 규약
