-- step: 007_drop_wire_id_columns
-- #75 PR 4: wire id 컬럼 폐기 — row PK (UUID) 가 wire id 역할 단일화.
-- A2A spec 의 contextId / taskId / messageId / artifactId 는 string 이지만
-- 우리는 UUID 발급 → str(uuid) 로 wire 에 표현. 외부 시스템 (M5+) 도 UUID
-- 발급한다는 가정.

DROP INDEX IF EXISTS idx_a2a_contexts_context;
DROP INDEX IF EXISTS idx_a2a_tasks_task_id;
DROP INDEX IF EXISTS idx_a2a_messages_message_id;

ALTER TABLE chats DROP COLUMN IF EXISTS message_id;
ALTER TABLE a2a_contexts DROP COLUMN IF EXISTS context_id;
ALTER TABLE a2a_tasks DROP COLUMN IF EXISTS task_id;
ALTER TABLE a2a_messages DROP COLUMN IF EXISTS message_id;
ALTER TABLE a2a_task_artifacts DROP COLUMN IF EXISTS artifact_id;
