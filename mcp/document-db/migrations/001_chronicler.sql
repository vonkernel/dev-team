-- 001_chronicler.sql — forward
-- Chronicler 의 3계층 (Task / Session / Item) + UUID 지원
-- 참조: docs/document-db-schema.md §1, §2, §3

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
