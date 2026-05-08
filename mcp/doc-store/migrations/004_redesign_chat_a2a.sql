-- 004_redesign_chat_a2a.sql — forward
-- #75: chat tier (sessions / chats / assignments) + A2A tier (a2a_contexts /
--      a2a_messages / a2a_tasks / a2a_task_status_updates / a2a_task_artifacts)
--      분리. 기존 agent_tasks / agent_sessions / agent_items 폐기.
--      cut-over — 마이그레이션 path 없음 (기존 데이터 폐기).
-- 참조: docs/proposal/knowledge-model.md §4.2,
--       docs/proposal/architecture-chat-protocol.md

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. 기존 3 테이블 폐기 + issues / wiki_pages 의 FK 정리
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE issues      DROP CONSTRAINT IF EXISTS issues_agent_task_id_fkey;
ALTER TABLE wiki_pages  DROP CONSTRAINT IF EXISTS wiki_pages_agent_task_id_fkey;

DROP TABLE IF EXISTS agent_items    CASCADE;
DROP TABLE IF EXISTS agent_sessions CASCADE;
DROP TABLE IF EXISTS agent_tasks    CASCADE;

-- 2. issues / wiki_pages 의 agent_task_id → assignment_id 로 의미 재정의

ALTER TABLE issues      RENAME COLUMN agent_task_id TO assignment_id;
ALTER TABLE wiki_pages  RENAME COLUMN agent_task_id TO assignment_id;

ALTER INDEX idx_issues_task      RENAME TO idx_issues_assignment;
ALTER INDEX idx_wiki_pages_task  RENAME TO idx_wiki_pages_assignment;

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. Chat tier — sessions / chats / assignments
-- ─────────────────────────────────────────────────────────────────────────────

-- 한 대화창 단위 (UG↔P/A). server-side 영속, FE 는 active session_id reference 만.
CREATE TABLE sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_endpoint  TEXT NOT NULL,                           -- 'primary' | 'architect'
    initiator       TEXT NOT NULL,                           -- 'user'
    counterpart     TEXT NOT NULL,                           -- agent name
    metadata        JSONB NOT NULL DEFAULT '{}',
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at        TIMESTAMPTZ
);
CREATE INDEX idx_sessions_endpoint ON sessions (agent_endpoint, started_at);

-- session 안의 한 발화. prev_chat_id 로 시간순 chain.
CREATE TABLE chats (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id    UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    prev_chat_id  UUID REFERENCES chats(id),
    role          TEXT NOT NULL CHECK (role IN ('user', 'agent', 'system')),
    sender        TEXT NOT NULL,
    content       JSONB NOT NULL,                            -- A2A parts 형태
    message_id    TEXT,                                      -- FE 또는 server 발급
    metadata      JSONB NOT NULL DEFAULT '{}',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_chats_session ON chats (session_id, created_at);
CREATE INDEX idx_chats_prev    ON chats (prev_chat_id);

-- 도메인 work item. P/A 가 chat 중 합의해 발급. 한 Assignment 안에 여러 A2A Task 발생 가능.
CREATE TABLE assignments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           TEXT NOT NULL,
    description     TEXT,
    status          TEXT NOT NULL DEFAULT 'open'
                    CHECK (status IN ('open', 'in_progress', 'done', 'cancelled')),
    owner_agent     TEXT,
    root_session_id UUID REFERENCES sessions(id) ON DELETE SET NULL,
    issue_refs      UUID[] NOT NULL DEFAULT '{}',
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_assignments_status       ON assignments (status);
CREATE INDEX idx_assignments_owner        ON assignments (owner_agent);
CREATE INDEX idx_assignments_root_session ON assignments (root_session_id);
CREATE INDEX idx_assignments_issue_refs   ON assignments USING GIN (issue_refs);

-- issues / wiki_pages 의 assignment_id 가 이제 assignments(id) 를 가리킴
ALTER TABLE issues
    ADD CONSTRAINT issues_assignment_id_fkey
    FOREIGN KEY (assignment_id) REFERENCES assignments(id) ON DELETE SET NULL;
ALTER TABLE wiki_pages
    ADD CONSTRAINT wiki_pages_assignment_id_fkey
    FOREIGN KEY (assignment_id) REFERENCES assignments(id) ON DELETE SET NULL;

-- ─────────────────────────────────────────────────────────────────────────────
-- 4. A2A tier — a2a_contexts / a2a_messages / a2a_tasks
--                + a2a_task_status_updates / a2a_task_artifacts
-- ─────────────────────────────────────────────────────────────────────────────

-- 두 에이전트 사이 대화 namespace. session 발 / assignment 발 / standalone (system trigger).
CREATE TABLE a2a_contexts (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    context_id           TEXT NOT NULL,                      -- A2A wire contextId
    initiator_agent      TEXT NOT NULL,
    counterpart_agent    TEXT NOT NULL,
    parent_session_id    UUID REFERENCES sessions(id) ON DELETE SET NULL,
    parent_assignment_id UUID REFERENCES assignments(id) ON DELETE SET NULL,
    trace_id             TEXT,
    topic                TEXT,
    metadata             JSONB NOT NULL DEFAULT '{}',
    started_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at             TIMESTAMPTZ
);
CREATE INDEX idx_a2a_contexts_context             ON a2a_contexts (context_id);
CREATE INDEX idx_a2a_contexts_trace               ON a2a_contexts (trace_id);
CREATE INDEX idx_a2a_contexts_parent_session      ON a2a_contexts (parent_session_id);
CREATE INDEX idx_a2a_contexts_parent_assignment   ON a2a_contexts (parent_assignment_id);

-- A2A Task — stateful long-running work tracking. SUBMITTED → COMPLETED.
CREATE TABLE a2a_tasks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id         TEXT NOT NULL,                           -- A2A wire taskId
    a2a_context_id  UUID NOT NULL REFERENCES a2a_contexts(id) ON DELETE CASCADE,
    state           TEXT NOT NULL
                    CHECK (state IN ('SUBMITTED', 'WORKING', 'COMPLETED',
                                     'INPUT_REQUIRED', 'FAILED')),
    submitted_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    assignment_id   UUID REFERENCES assignments(id) ON DELETE SET NULL,
    metadata        JSONB NOT NULL DEFAULT '{}'
);
CREATE INDEX idx_a2a_tasks_context     ON a2a_tasks (a2a_context_id, submitted_at);
CREATE INDEX idx_a2a_tasks_state       ON a2a_tasks (state);
CREATE INDEX idx_a2a_tasks_assignment  ON a2a_tasks (assignment_id);
CREATE INDEX idx_a2a_tasks_task_id     ON a2a_tasks (task_id);

-- A2A Message — trivial Message (a2a_task_id NULL) 또는 Task.history (a2a_task_id 채움).
CREATE TABLE a2a_messages (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id        TEXT NOT NULL,                         -- A2A wire messageId
    a2a_context_id    UUID NOT NULL REFERENCES a2a_contexts(id) ON DELETE CASCADE,
    a2a_task_id       UUID REFERENCES a2a_tasks(id) ON DELETE SET NULL,
    role              TEXT NOT NULL CHECK (role IN ('user', 'agent', 'system')),
    sender            TEXT NOT NULL,
    parts             JSONB NOT NULL,
    prev_message_id   UUID REFERENCES a2a_messages(id),
    metadata          JSONB NOT NULL DEFAULT '{}',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_a2a_messages_context     ON a2a_messages (a2a_context_id, created_at);
CREATE INDEX idx_a2a_messages_task        ON a2a_messages (a2a_task_id);
CREATE INDEX idx_a2a_messages_message_id  ON a2a_messages (message_id);
CREATE INDEX idx_a2a_messages_prev        ON a2a_messages (prev_message_id);

-- A2A Task 의 state transition 로그.
CREATE TABLE a2a_task_status_updates (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    a2a_task_id     UUID NOT NULL REFERENCES a2a_tasks(id) ON DELETE CASCADE,
    state           TEXT NOT NULL
                    CHECK (state IN ('SUBMITTED', 'WORKING', 'COMPLETED',
                                     'INPUT_REQUIRED', 'FAILED')),
    transitioned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reason          TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}'
);
CREATE INDEX idx_a2a_task_status_updates_task
    ON a2a_task_status_updates (a2a_task_id, transitioned_at);

-- A2A Task 의 산출물 (Artifact).
CREATE TABLE a2a_task_artifacts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    a2a_task_id     UUID NOT NULL REFERENCES a2a_tasks(id) ON DELETE CASCADE,
    artifact_id     TEXT NOT NULL,                           -- A2A wire artifactId
    name            TEXT,
    parts           JSONB NOT NULL,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_a2a_task_artifacts_task ON a2a_task_artifacts (a2a_task_id);
