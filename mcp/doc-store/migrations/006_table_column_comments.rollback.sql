-- step: 006_table_column_comments.rollback
-- 추가한 COMMENT 들을 제거 (NULL 로 set).

COMMENT ON TABLE sessions IS NULL;
COMMENT ON TABLE chats IS NULL;
COMMENT ON COLUMN chats.session_id IS NULL;
COMMENT ON COLUMN chats.prev_chat_id IS NULL;
COMMENT ON COLUMN chats.message_id IS NULL;
COMMENT ON TABLE assignments IS NULL;
COMMENT ON COLUMN assignments.root_session_id IS NULL;

COMMENT ON TABLE a2a_contexts IS NULL;
COMMENT ON COLUMN a2a_contexts.context_id IS NULL;
COMMENT ON COLUMN a2a_contexts.parent_session_id IS NULL;
COMMENT ON COLUMN a2a_contexts.parent_assignment_id IS NULL;
COMMENT ON COLUMN a2a_contexts.trace_id IS NULL;
COMMENT ON COLUMN a2a_contexts.ended_at IS NULL;
COMMENT ON TABLE a2a_messages IS NULL;
COMMENT ON COLUMN a2a_messages.a2a_context_id IS NULL;
COMMENT ON COLUMN a2a_messages.a2a_task_id IS NULL;
COMMENT ON COLUMN a2a_messages.message_id IS NULL;
COMMENT ON TABLE a2a_tasks IS NULL;
COMMENT ON COLUMN a2a_tasks.a2a_context_id IS NULL;
COMMENT ON COLUMN a2a_tasks.assignment_id IS NULL;
COMMENT ON COLUMN a2a_tasks.task_id IS NULL;
COMMENT ON TABLE a2a_task_status_updates IS NULL;
COMMENT ON COLUMN a2a_task_status_updates.a2a_task_id IS NULL;
COMMENT ON TABLE a2a_task_artifacts IS NULL;
COMMENT ON COLUMN a2a_task_artifacts.a2a_task_id IS NULL;

COMMENT ON TABLE issues IS NULL;
COMMENT ON COLUMN issues.assignment_id IS NULL;
COMMENT ON TABLE wiki_pages IS NULL;
COMMENT ON COLUMN wiki_pages.assignment_id IS NULL;
