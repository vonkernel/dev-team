-- 002_issues.sql — forward
-- 외부 이슈 트래커 mirror (Epic / Story / Task type)
-- 참조: docs/document-db-schema.md §4

CREATE TABLE issues (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_task_id   UUID REFERENCES agent_tasks(id) ON DELETE SET NULL,
    type            TEXT NOT NULL CHECK (type IN ('epic', 'story', 'task')),
    title           TEXT NOT NULL,
    body_md         TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft', 'confirmed', 'cancelled')),
    parent_issue_id UUID REFERENCES issues(id) ON DELETE SET NULL,
    labels          TEXT[] NOT NULL DEFAULT '{}',
    external_refs   JSONB NOT NULL DEFAULT '{}',
    last_synced_at  TIMESTAMPTZ,
    metadata        JSONB NOT NULL DEFAULT '{}',
    version         INT NOT NULL DEFAULT 1,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_issues_task        ON issues (agent_task_id);
CREATE INDEX idx_issues_type_status ON issues (type, status);
CREATE INDEX idx_issues_parent      ON issues (parent_issue_id);
CREATE INDEX idx_issues_external    ON issues USING GIN (external_refs);
CREATE INDEX idx_issues_labels      ON issues USING GIN (labels);
