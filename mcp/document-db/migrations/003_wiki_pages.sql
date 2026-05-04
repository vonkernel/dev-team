-- 003_wiki_pages.sql — forward
-- 위키 문서 mirror (PRD / ADR / business_rule 등 page_type 별 통합)
-- 참조: docs/document-db-schema.md §5

CREATE TABLE wiki_pages (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_task_id       UUID REFERENCES agent_tasks(id) ON DELETE SET NULL,
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
CREATE INDEX idx_wiki_pages_type_status ON wiki_pages (page_type, status);
CREATE INDEX idx_wiki_pages_task        ON wiki_pages (agent_task_id);
CREATE INDEX idx_wiki_pages_external    ON wiki_pages USING GIN (external_refs);
CREATE INDEX idx_wiki_pages_refs_issues ON wiki_pages USING GIN (references_issues);
CREATE INDEX idx_wiki_pages_refs_pages  ON wiki_pages USING GIN (references_pages);
