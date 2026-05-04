# Document DB MCP — AI 에이전트 작업 규칙

본 모듈을 수정하는 AI 에이전트 (Claude / 기타) 가 따라야 할 규약. root `CLAUDE.md`
의 일반 규약 (SOLID / 모듈 코드 구조 / 포트 컨벤션 등) 위에 본 모듈 한정 사항.

---

## 1. 본 모듈의 역할

PostgreSQL `dev_team` DB 의 thin CRUD 래퍼. **비즈니스 로직 없음** — 들어온 그대로 저장 / 꺼내 줌.

| 항목 | 값 |
|---|---|
| Transport | streamable HTTP (MCP spec 2025-06-18) |
| 호스트 포트 | **9100** |
| 컨테이너 포트 | 8000 (uvicorn) |
| DB | Postgres 단일 인스턴스의 `dev_team` DB (langgraph DB 와 분리) |
| Migration | yoyo-migrations, MCP 부팅 시 자동 적용 |

---

## 2. Collection 5종 — 절대 추가 / 변경은 별 이슈

| Collection | 정체성 |
|---|---|
| `agent_tasks` | 작업 단위 (Chronicler "Task") |
| `agent_sessions` | 한 task 안의 대화 흐름 |
| `agent_items` | 한 session 안의 개별 메시지 |
| `issues` | 외부 이슈 트래커 mirror (Epic/Story/Task type) |
| `wiki_pages` | 위키 문서 mirror (PRD/ADR/business_rule 등 type) |

**원칙**:
- 새 collection 추가 = **별 이슈 + 사용자 컨펌** 후. 즉흥 추가 금지.
- 기존 collection 의 컬럼 변경 = **마이그레이션 신규 파일 작성** (기존 SQL 수정 X).
- PRD 는 별 entity 안 만든다. `wiki_pages.page_type='prd'` 로 통합.

---

## 3. 새 collection 추가 시 절차 (OCP)

```
1. mcp/document-db/migrations/NNN_<name>.sql        새 마이그레이션 (롤백 SQL 포함)
2. src/document_db_mcp/schemas/<name>.py            Pydantic 모델 (Create / Update / Read)
3. src/document_db_mcp/repositories/<name>.py       AbstractRepository 상속 + 특수 쿼리
4. src/document_db_mcp/tools/<name>.py              MCP tool 함수 (5 op generic + 특수 도구)
5. src/document_db_mcp/tools/__init__.py            register 1줄 추가
```

**기존 파일 수정 0줄** 이 OCP 충족 시그널. 수정이 필요해진다면 abstraction 부족 → 다시 검토.

---

## 4. 노출 도구 면 — collection 별 5 op

각 collection 이 동일한 5 op 를 노출. generic 구현 (`tools/_generic.py`) 위에 collection 별 모듈이 등록.

| 도구 | 시그니처 | 비고 |
|---|---|---|
| `{collection}.upsert` | `(doc) → DocRef` | id 있으면 update, 없으면 insert. version 컬럼 있으면 optimistic locking |
| `{collection}.get` | `(id) → Doc \| null` | 단건 |
| `{collection}.list` | `(filter, limit, offset, order_by) → list[Doc]` | filter 는 jsonb path 쿼리 가능 |
| `{collection}.delete` | `(id) → bool` | hard delete |
| `{collection}.count` | `(filter) → int` | 페이지네이션용 |

특수 도구 (Chronicler 의 read 패턴 전용):
- `agent_items.list_by_session(session_id) → ordered list` (prev_item_id 체인)
- `agent_sessions.list_by_task(agent_task_id) → list`
- `agent_sessions.find_by_context(context_id) → Session | null`

---

## 5. Repository 패턴 — 절대 우회 금지

```python
# tools/<name>.py — 옳음
async def upsert(repo: IssueRepository, doc: IssueCreate) -> IssueRef:
    return await repo.upsert(doc)

# tools/<name>.py — 금지 (DIP 위반)
async def upsert_bad(pool: asyncpg.Pool, doc: IssueCreate) -> IssueRef:
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO issues ...")  # ← repository 우회
```

- `tools/` 코드는 `repositories/` 만 의존. asyncpg 직접 호출 금지.
- repository 가 schema 검증 / SQL 조립 / 트랜잭션 책임 독점.
- 새 쿼리 패턴이 필요하면 repository 에 메서드 추가 (tools 에 SQL 흩뿌리기 X).

---

## 6. Migration 규약 (yoyo)

- 파일명: `NNN_short_name.sql` (NNN 은 0-padding 3자리, e.g. `001_chronicler.sql`)
- 각 파일은 **반드시** `-- step:` 으로 forward / rollback 분리
- 적용 순서는 NNN 사전순 — 번호 충돌 금지
- 적용 시점: MCP 서버 부팅 직후 (server.py lifespan) 자동 실행
- **기존 파일 수정 금지** — 수정 사항은 새 마이그레이션으로

```sql
-- step: 001_chronicler
CREATE TABLE agent_tasks (...);

-- step: 001_chronicler.rollback
DROP TABLE agent_tasks;
```

---

## 7. 테스트 규약

- Repository 단위 = `pytest-asyncio` + `testcontainers[postgres]` 로 실 Postgres
- Tool 단위 = Repository mock
- 통합 = `docker compose up` 후 streamable HTTP 호출 (수동 또는 e2e 스크립트)

테스트 위치:
```
mcp/document-db/tests/
├── test_repositories/    # 실 Postgres
├── test_tools/           # mock repository
└── test_migrations/      # SQL 적용 / 롤백 검증
```

---

## 8. 절대 금지 사항

- **ORM 도입** (SQLAlchemy / Tortoise 등). asyncpg + raw SQL 만.
- **repository 우회 직접 SQL**.
- **schema validation 우회** (raw dict 외부 노출).
- **모듈 레벨 전역 connection / pool**. lifespan + DI 만.
- **postgres-init 에 본 모듈의 schema 작성**. schema 는 본 모듈의 마이그레이션이 담당.
- **`langgraph` DB 직접 접근**. `dev_team` DB 만.

---

## 9. 관련 문서

- 본 root: [`/CLAUDE.md`](../../CLAUDE.md) — 프로젝트 일반 규약
- 스키마 본문: [`docs/document-db-schema.md`](../../docs/document-db-schema.md)
- 이슈 #35 의 design proposal — 본 모듈 첫 commit 의 근거
