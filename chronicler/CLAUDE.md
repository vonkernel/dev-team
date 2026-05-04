# Chronicler (CHR) — AI 에이전트 작업 규칙

본 모듈을 수정하는 AI 에이전트 (Claude / 기타) 가 따라야 할 규약. root
`CLAUDE.md` 위에 본 모듈 한정 사항.

---

## 1. 정체성

- **에이전트가 아님.** LangGraph / LLM / Role Config / A2A 일체 미사용.
- 단일 Python 스크립트 (long-lived process). Valkey Stream consumer + Document
  DB MCP 클라이언트 두 가지로만 구성.
- 책임: **A2A 대화 이벤트 수집 → Document DB 영속화**.

자세한 시스템 위치 / 흐름은 [`docs/proposal.md`](../docs/proposal.md) §2.6 참조.

---

## 2. 데이터 흐름

```
publisher (UG / P / ...)  →  Valkey Stream "a2a-events"  →  CHR  →  Document DB MCP
       (XADD)                (Consumer Group "chronicler")  (XREADGROUP / 처리 / XACK)
```

이벤트 종류 (3): `session.start` / `item.append` / `session.end`.
스키마는 `dev_team_shared.event_bus.events` (Pydantic). publisher 와 contract.

---

## 3. Idempotency / 재시작 내구성

- 이벤트마다 `event_id` (UUID) — publisher 가 부여
- CHR 가 처리 완료 후 `XACK` — 그 사이 죽으면 PEL 의 미처리 메시지 재전달
- **재시도 시 중복 처리 방지**: agent_session.find_by_context + agent_item 의
  message_id 중복 체크로 흡수 (idempotent CRUD 패턴)
- DB 트랜잭션 내 다중 쓰기는 본 모듈 책임 X — Document DB MCP 가 단순 CRUD

---

## 4. Fallback — agent_task 미지정 처리

publisher (UG / P) 가 `agent_task_id` 모르고 보낼 수 있음 (#34 단계의 P 는 task
개념 미보유. #39 에서 도입). CHR 가 처리:

- `agent_task_id` 없는 `session.start` → 임시 task 생성 (title=
  `"<initiator> ↔ <counterpart> @ <timestamp>"`) 후 그 id 로 session 생성
- #39 이후 P 가 정식 task 발급하면 fallback 안 탐

본 fallback 은 **M3 한정**. M5+ 에서는 publisher 가 항상 task_id 채워 보낼 것을
가정 (M3 fallback 제거 검토).

---

## 5. 절대 금지 사항

- **LangGraph / LLM 도입** — CHR 는 thin transformer. 추론 책임은 L / 에이전트
- **Document DB 직접 연결** — 반드시 MCP 경유 (`shared.mcp_client`)
- **Valkey 외 다른 broker 추가** — 본 마일스톤 범위 밖
- **agent_items 의 update / 수정** — items 는 immutable

---

## 6. 의존 / 운영

| 의존 | 용도 |
|---|---|
| `redis>=7.4.0` (asyncio) | Valkey Streams 클라이언트 |
| `mcp>=1.27.0` | streamable HTTP MCP client |
| `dev_team_shared.event_bus` | 이벤트 schema |
| `dev_team_shared.mcp_client` | MCP 클라이언트 wrapper |

env:
- `VALKEY_URL` — `redis://valkey:6379`
- `DOCUMENT_DB_MCP_URL` — `http://document-db-mcp:8000/mcp`
- `CHRONICLER_CONSUMER_GROUP` — 기본 `chronicler`
- `CHRONICLER_CONSUMER_NAME` — 기본 hostname (k8s 시 pod name)

---

## 7. 관련 문서

- root [`/CLAUDE.md`](../CLAUDE.md) — 프로젝트 일반 규약
- [`docs/proposal.md`](../docs/proposal.md) §2.6 — Chronicler 정체성 / Task/Session/Item
- [`docs/document-db-schema.md`](../docs/document-db-schema.md) — 영속 대상 스키마
