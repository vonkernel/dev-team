-- step: 007_drop_wire_id_columns.rollback
-- 컬럼 복원 (값은 복원 불가 — drop 시 손실).

ALTER TABLE chats ADD COLUMN message_id TEXT;
ALTER TABLE a2a_contexts ADD COLUMN context_id TEXT;
ALTER TABLE a2a_tasks ADD COLUMN task_id TEXT;
ALTER TABLE a2a_messages ADD COLUMN message_id TEXT;
ALTER TABLE a2a_task_artifacts ADD COLUMN artifact_id TEXT;

CREATE INDEX idx_a2a_contexts_context ON a2a_contexts (context_id);
CREATE INDEX idx_a2a_tasks_task_id ON a2a_tasks (task_id);
CREATE INDEX idx_a2a_messages_message_id ON a2a_messages (message_id);
