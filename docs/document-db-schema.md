# Document DB Schema (`dev_team` DB)

본 문서는 PostgreSQL `dev_team` DB 의 스키마를 정의한다. 실제 마이그레이션은
`mcp/document-db/migrations/` 의 SQL 파일이며, 본 문서는 **결정 의도 + 컬럼별
의미 + 인덱스 근거** 를 함께 기록한다.

`langgraph` DB 와는 같은 인스턴스의 다른 DB 로 분리되어 있다 (이슈 #20).

---

## 0. 명명 / 통일 규약

- **테이블 / 컬럼**: `snake_case`
- **PK**: 모두 `id UUID DEFAULT gen_random_uuid()` (Postgres `pgcrypto` 또는 `uuid-ossp`)
- **시간**: 모두 `TIMESTAMPTZ`. `created_at` / `updated_at` 두 컬럼 default `NOW()`
- **JSONB 컬럼**: GIN 인덱스로 path 쿼리 가능
- **enum 류**: TEXT + CHECK 제약 (Postgres native ENUM 은 ALTER 비용 큼)
- **외부 도구 mirror**: `external_refs JSONB DEFAULT '{}'` + `last_synced_at TIMESTAMPTZ`
- **status lifecycle**: `draft | confirmed | cancelled` (TEXT + CHECK)

---

## 1. `agent_tasks` — 작업 단위

**역할**: 에이전트가 처리하는 한 단위 일. Chronicler 의 Task 계층 (proposal §2.6) 그대로. 모든 다른 entity (issue / wiki / session) 의 묶음 키.

```sql
CREATE TABLE agent_tasks (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title         TEXT NOT NULL,
    description   TEXT,
    status        TEXT NOT NULL DEFAULT 'open'
                  CHECK (status IN ('open', 'in_progress', 'done', 'cancelled')),
    owner_agent   TEXT,                    -- 'primary' | 'architect' | ...
    issue_refs    UUID[] NOT NULL DEFAULT '{}',  -- issues.id 의 array
    metadata      JSONB NOT NULL DEFAULT '{}',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_agent_tasks_status   ON agent_tasks (status);
CREATE INDEX idx_agent_tasks_owner    ON agent_tasks (owner_agent);
CREATE INDEX idx_agent_tasks_issues   ON agent_tasks USING GIN (issue_refs);
```

| 컬럼 | 의미 |
|---|---|
| `status` | 작업 진행 상태. `open` (생성됨, 시작 전) / `in_progress` / `done` / `cancelled` |
| `owner_agent` | 현재 책임 에이전트. 위임 시 갱신 |
| `issue_refs` | 본 task 가 처리하는 외부 issue 들 (FK 가 아닌 array — issue 가 여러 task 에 걸칠 수 있음) |
| `metadata` | 자유 확장. 검색되지 않을 메타데이터 |

---

## 2. `agent_sessions` — 대화 흐름

**역할**: 한 agent_task 안에서 진행되는 한 대화 흐름 (proposal §2.6 Session). A2A `contextId` 와 1:1.

```sql
CREATE TABLE agent_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_task_id   UUID NOT NULL REFERENCES agent_tasks(id) ON DELETE CASCADE,
    initiator       TEXT NOT NULL,          -- 'user' | 'primary' | 'architect' | ...
    counterpart     TEXT NOT NULL,
    context_id      TEXT NOT NULL,          -- A2A contextId
    trace_id        TEXT,                   -- 시스템 전체 추적 (#32)
    topic           TEXT,                   -- 자유 라벨
    metadata        JSONB NOT NULL DEFAULT '{}',
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at        TIMESTAMPTZ
);

CREATE INDEX idx_agent_sessions_task    ON agent_sessions (agent_task_id, started_at);
CREATE INDEX idx_agent_sessions_context ON agent_sessions (context_id);
CREATE INDEX idx_agent_sessions_trace   ON agent_sessions (trace_id);
```

| 컬럼 | 의미 |
|---|---|
| `initiator` / `counterpart` | A2A 호출의 양 끝. user / primary / architect / ... |
| `context_id` | A2A `Message.contextId` — 한 boundary 안의 conversation |
| `trace_id` | 시스템 전체 추적 ID (#32 의 `X-A2A-Trace-Id` 헤더) |
| `ended_at` | session 종료 시각. NULL 이면 진행 중 |

L 의 `get_chronicler_log_by_context(context_id)` 는 이 테이블 lookup → 해당 session 의 items 반환.

---

## 3. `agent_items` — 개별 메시지

**역할**: session 안의 한 메시지 (proposal §2.6 Item). prev_item_id 로 시간순 chain.

```sql
CREATE TABLE agent_items (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_session_id  UUID NOT NULL REFERENCES agent_sessions(id) ON DELETE CASCADE,
    prev_item_id      UUID REFERENCES agent_items(id),
    role              TEXT NOT NULL
                      CHECK (role IN ('user', 'agent', 'system')),
    sender            TEXT NOT NULL,         -- 구체 발신자 ('primary' / 'architect' / 'user' 등)
    content           JSONB NOT NULL,        -- A2A Message.parts 그대로
    message_id        TEXT,                  -- 원본 A2A messageId (디버그용)
    metadata          JSONB NOT NULL DEFAULT '{}',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_agent_items_session    ON agent_items (agent_session_id, created_at);
CREATE INDEX idx_agent_items_prev       ON agent_items (prev_item_id);
```

| 컬럼 | 의미 |
|---|---|
| `prev_item_id` | 이전 item — 대화 순서 추적 |
| `role` | A2A `Message.role` 매핑 (user / agent / system) |
| `sender` | 어느 에이전트 / 사용자 |
| `content` | A2A `Message.parts` 의 JSON 직렬 (text / data / etc) |

---

## 4. `issues` — 외부 이슈 트래커 mirror

**역할**: 사용자가 컨펌한 Epic / Story / Task. document db 가 본질, GitHub Issue 등 외부 도구로 단방향 sync (C2 결정).

```sql
CREATE TABLE issues (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_task_id   UUID REFERENCES agent_tasks(id),
    type            TEXT NOT NULL
                    CHECK (type IN ('epic', 'story', 'task')),
    title           TEXT NOT NULL,
    body_md         TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft', 'confirmed', 'cancelled')),
    parent_issue_id UUID REFERENCES issues(id),
    labels          TEXT[] NOT NULL DEFAULT '{}',
    external_refs   JSONB NOT NULL DEFAULT '{}',
    last_synced_at  TIMESTAMPTZ,
    metadata        JSONB NOT NULL DEFAULT '{}',
    version         INT NOT NULL DEFAULT 1,    -- optimistic concurrency
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_issues_task          ON issues (agent_task_id);
CREATE INDEX idx_issues_type_status   ON issues (type, status);
CREATE INDEX idx_issues_parent        ON issues (parent_issue_id);
CREATE INDEX idx_issues_external      ON issues USING GIN (external_refs);
```

| 컬럼 | 의미 |
|---|---|
| `type` | `epic` / `story` / `task` — C3 결정. 어댑터별 매핑 (GitHub = label) |
| `status` | `draft` (대화 중) → `confirmed` (사용자 컨펌, external sync 완료) → `cancelled` |
| `parent_issue_id` | Epic → Story 계층 |
| `labels` | 자유 라벨 array |
| `external_refs` | `{"github": {"issue_number": 1, "node_id": "..."}}` 형식 |
| `version` | optimistic concurrency. update 시 `WHERE version = ? AND id = ?` |

---

## 5. `wiki_pages` — 위키 문서 mirror

**역할**: 사용자가 컨펌한 위키 문서 (PRD / ADR / business_rule 등). 본질은 db, GitHub Wiki 로 단방향 sync.

```sql
CREATE TABLE wiki_pages (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_task_id       UUID REFERENCES agent_tasks(id),
    page_type           TEXT NOT NULL
                        CHECK (page_type IN (
                            'prd', 'business_rule', 'data_model',
                            'adr', 'api_contract',
                            'glossary', 'runbook', 'generic'
                        )),
    slug                TEXT NOT NULL UNIQUE,
    title               TEXT NOT NULL,
    content_md          TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft', 'confirmed', 'cancelled')),
    author_agent        TEXT,
    references_issues   UUID[] NOT NULL DEFAULT '{}',
    references_pages    UUID[] NOT NULL DEFAULT '{}',
    structured          JSONB NOT NULL DEFAULT '{}',
    external_refs       JSONB NOT NULL DEFAULT '{}',
    last_synced_at      TIMESTAMPTZ,
    metadata            JSONB NOT NULL DEFAULT '{}',
    version             INT NOT NULL DEFAULT 1,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_wiki_pages_type_status   ON wiki_pages (page_type, status);
CREATE INDEX idx_wiki_pages_task          ON wiki_pages (agent_task_id);
CREATE INDEX idx_wiki_pages_external      ON wiki_pages USING GIN (external_refs);
CREATE INDEX idx_wiki_pages_refs_issues   ON wiki_pages USING GIN (references_issues);
CREATE INDEX idx_wiki_pages_refs_pages    ON wiki_pages USING GIN (references_pages);
```

| 컬럼 | 의미 |
|---|---|
| `page_type` | 문서 분류. 각 type 별 작성 가이드는 작성 주체 에이전트의 `resources/wiki-authoring-guide.md` |
| `slug` | URL-friendly id. wiki path 와 매핑. UNIQUE |
| `content_md` | 사람이 읽는 markdown 본문 |
| `structured` | type 별 구조화 데이터 (예: ADR 의 alternatives, data_model 의 entities). 기계 쿼리용 |
| `references_issues` | 관련 issue id array |
| `references_pages` | 관련 wiki page id array |
| `version` | optimistic concurrency |

### `page_type` enum

| type | 작성 주체 | 비고 |
|---|---|---|
| `prd` | P | Product Requirements Document. 한 프로젝트 1개 |
| `business_rule` | P | 비즈니스 정책 / 규칙 |
| `data_model` | P, A | 데이터 모델. P 가 초기본, A 가 정밀화 |
| `adr` | A | Architecture Decision Record |
| `api_contract` | A | API 계약 |
| `glossary` | P, A | 용어집 |
| `runbook` | A | 운영 절차 |
| `generic` | 모두 | 위 카테고리 외 |

---

## 6. 향후 확장 (M5+)

- `agent_tasks` 의 sub-task hierarchy (parent_task_id) — A 가 Eng/QA 배분 시
- `prds` 의 versioning (full history) — 현재는 단일 row 갱신
- 풀텍스트 검색 (`tsvector` 컬럼) — wiki / item content
- `audit_log` 테이블 — 모든 entity 의 변경 이력

---

## 7. 마이그레이션 파일 매핑

| 파일 | 다루는 entities |
|---|---|
| `001_chronicler.sql` | agent_tasks, agent_sessions, agent_items |
| `002_issues.sql` | issues |
| `003_wiki_pages.sql` | wiki_pages |

각 파일은 forward + rollback step 모두 포함. yoyo-migrations 가 `_yoyo_migration` 테이블로 적용 상태 추적.
