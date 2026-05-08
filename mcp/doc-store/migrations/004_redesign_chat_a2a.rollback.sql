-- 004_redesign_chat_a2a.rollback.sql
-- 새 8 테이블 폐기 → 기존 3 테이블 (agent_tasks / sessions / items) 재생성.
-- assignment_id 컬럼은 다시 agent_task_id 로. 기존 데이터는 복원 불가 (cut-over).

-- 1. issues / wiki_pages 의 assignment_id FK 제거 + 컬럼명 복귀

ALTER TABLE issues      DROP CONSTRAINT IF EXISTS issues_assignment_id_fkey;
ALTER TABLE wiki_pages  DROP CONSTRAINT IF EXISTS wiki_pages_assignment_id_fkey;

ALTER TABLE issues      RENAME COLUMN assignment_id TO agent_task_id;
ALTER TABLE wiki_pages  RENAME COLUMN assignment_id TO agent_task_id;

ALTER INDEX idx_issues_assignment      RENAME TO idx_issues_task;
ALTER INDEX idx_wiki_pages_assignment  RENAME TO idx_wiki_pages_task;

-- 2. 새 8 테이블 폐기

DROP TABLE IF EXISTS a2a_task_artifacts      CASCADE;
DROP TABLE IF EXISTS a2a_task_status_updates CASCADE;
DROP TABLE IF EXISTS a2a_messages            CASCADE;
DROP TABLE IF EXISTS a2a_tasks               CASCADE;
DROP TABLE IF EXISTS a2a_contexts            CASCADE;
DROP TABLE IF EXISTS chats                   CASCADE;
DROP TABLE IF EXISTS assignments             CASCADE;
DROP TABLE IF EXISTS sessions                CASCADE;

-- 3. 기존 3 테이블 재생성 (001_chronicler.sql 의 forward 와 동일)

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE agent_tasks (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title         TEXT NOT NULL,
    description   TEXT,
    status        TEXT NOT NULL DEFAULT 'open'
                  CHECK (status IN ('open', 'in_progress', 'done', 'cancelled')),
    owner_agent   TEXT,
    issue_refs    UUID[] NOT NULL DEFAULT '{}',
    metadata      JSONB NOT NULL DEFAULT '{}',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_agent_tasks_status ON agent_tasks (status);
CREATE INDEX idx_agent_tasks_owner  ON agent_tasks (owner_agent);
CREATE INDEX idx_agent_tasks_issues ON agent_tasks USING GIN (issue_refs);

CREATE TABLE agent_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_task_id   UUID NOT NULL REFERENCES agent_tasks(id) ON DELETE CASCADE,
    initiator       TEXT NOT NULL,
    counterpart     TEXT NOT NULL,
    context_id      TEXT NOT NULL,
    trace_id        TEXT,
    topic           TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}',
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at        TIMESTAMPTZ
);
CREATE INDEX idx_agent_sessions_task    ON agent_sessions (agent_task_id, started_at);
CREATE INDEX idx_agent_sessions_context ON agent_sessions (context_id);
CREATE INDEX idx_agent_sessions_trace   ON agent_sessions (trace_id);

CREATE TABLE agent_items (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_session_id  UUID NOT NULL REFERENCES agent_sessions(id) ON DELETE CASCADE,
    prev_item_id      UUID REFERENCES agent_items(id),
    role              TEXT NOT NULL CHECK (role IN ('user', 'agent', 'system')),
    sender            TEXT NOT NULL,
    content           JSONB NOT NULL,
    message_id        TEXT,
    metadata          JSONB NOT NULL DEFAULT '{}',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_agent_items_session ON agent_items (agent_session_id, created_at);
CREATE INDEX idx_agent_items_prev    ON agent_items (prev_item_id);

-- 4. issues / wiki_pages 의 FK 복원

ALTER TABLE issues
    ADD CONSTRAINT issues_agent_task_id_fkey
    FOREIGN KEY (agent_task_id) REFERENCES agent_tasks(id) ON DELETE SET NULL;
ALTER TABLE wiki_pages
    ADD CONSTRAINT wiki_pages_agent_task_id_fkey
    FOREIGN KEY (agent_task_id) REFERENCES agent_tasks(id) ON DELETE SET NULL;
