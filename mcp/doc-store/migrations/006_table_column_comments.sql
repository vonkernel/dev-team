-- step: 006_table_column_comments
-- #75: schema 의 의도 (containment vs ref 관계 / 종료 모델 / source 추적)
--      를 PostgreSQL COMMENT 로 박아 schema 만 읽어도 의도 파악 가능하게.
--      psql `\d+ <table>` 또는 information_schema 로 노출됨.

-- ─────────────────────────────────────────────────────────────────────────────
-- Chat tier
-- ─────────────────────────────────────────────────────────────────────────────

COMMENT ON TABLE sessions IS
    'UG↔P/A 한 대화창 (chat tier). 종료 개념 없음 — 사용자가 언제든 재개 '
    '(Slack DM / ChatGPT 류). ended_at 컬럼 없음. archive 가 필요해지면 '
    '별 컬럼 (archived_at) 으로.';

COMMENT ON TABLE chats IS
    'session 안의 한 발화 (immutable). session 에 containment 종속 '
    '(NOT NULL FK + CASCADE) — session 없이 존재 X.';

COMMENT ON COLUMN chats.session_id IS
    'containment FK to sessions — session 없이 존재 X.';
COMMENT ON COLUMN chats.prev_chat_id IS
    'self-ref to chats — 시간순 chain. NULL 이면 session 의 첫 발화.';
COMMENT ON COLUMN chats.message_id IS
    'publisher 발급 wire id (FE / server). idempotency dedup key.';

COMMENT ON TABLE assignments IS
    'P/A 가 chat 중 합의해 발급한 도메인 work item. session 발이면 '
    'root_session_id 채움 (ref backlink), 독립 발급도 가능 (NULL).';

COMMENT ON COLUMN assignments.root_session_id IS
    'ref backlink to sessions — 어디서 비롯된 work item 인지 추적용. '
    'NULL 허용 (session 무관 standalone assignment 가능). SET NULL on delete.';

-- ─────────────────────────────────────────────────────────────────────────────
-- A2A tier
-- ─────────────────────────────────────────────────────────────────────────────

COMMENT ON TABLE a2a_contexts IS
    '두 에이전트 사이 대화 namespace (A2A wire contextId 와 1:1). '
    'session / assignment 발이면 parent_*_id 채움 (ref backlink), '
    '둘 다 NULL 이면 standalone (agent autonomous / 외부 system trigger 발). '
    '종료는 agent 가 결정 — agent 가 "inter-agent 대화 마무리" 판단 시 '
    'a2a.context.end 발화. RPC 단위 아님 (한 contextId 위 다중 RPC 누적).';

COMMENT ON COLUMN a2a_contexts.context_id IS
    'A2A wire contextId. 호출자가 발급한 string identifier. 우리 구현은 '
    'LangGraph thread_id 로 매핑해 체크포인터 thread 격리.';
COMMENT ON COLUMN a2a_contexts.parent_session_id IS
    'ref backlink to sessions — chat 발 trace 만 채움. containment 아님 '
    '(standalone a2a_context 가능 — session 종료에 영향 받지 않음).';
COMMENT ON COLUMN a2a_contexts.parent_assignment_id IS
    'ref backlink to assignments — assignment 진행 발 trace 만 채움. '
    'containment 아님.';
COMMENT ON COLUMN a2a_contexts.trace_id IS
    'boundary 가로지르는 한 의도의 추적 ID. 시작점 셋 (사용자 / agent '
    'autonomous / 외부 system trigger) 어디든 같은 trace_id 가 따라다님. '
    'HTTP X-A2A-Trace-Id 헤더로 propagate.';
COMMENT ON COLUMN a2a_contexts.ended_at IS
    'agent 가 inter-agent 대화 마무리 판단 시 set. NULL 이면 활성 (장기 '
    '대화 / agent 가 종료 미결정).';

COMMENT ON TABLE a2a_messages IS
    'A2A Message (immutable). a2a_task_id NULL 이면 trivial / negotiation '
    'Message, 채워지면 Task.history 의 일원. a2a_context 에 containment '
    '종속 (NOT NULL FK + CASCADE).';

COMMENT ON COLUMN a2a_messages.a2a_context_id IS
    'containment FK to a2a_contexts — context 없이 존재 X.';
COMMENT ON COLUMN a2a_messages.a2a_task_id IS
    'ref backlink to a2a_tasks — Task.history 의 일원이면 채움. NULL 이면 '
    'standalone trivial Message (Task wrap 없는 응답). SET NULL on delete.';
COMMENT ON COLUMN a2a_messages.message_id IS
    'A2A wire messageId. publisher 발급, idempotency dedup key.';

COMMENT ON TABLE a2a_tasks IS
    'A2A Task (stateful work, SUBMITTED → COMPLETED 등). a2a_context 에 '
    'containment 종속. 도메인 Assignment 와 다른 객체 — 한 Assignment 안에 '
    '여러 a2a_task 가능 (Assignment = 도메인 work item, a2a_task = wire-level '
    '한 호출 진행 추적).';

COMMENT ON COLUMN a2a_tasks.a2a_context_id IS
    'containment FK to a2a_contexts — context 없이 존재 X.';
COMMENT ON COLUMN a2a_tasks.assignment_id IS
    'ref backlink to assignments — 어느 도메인 work item 의 일환인지 '
    '추적용. NULL 허용 (assignment 무관 standalone a2a_task 가능).';
COMMENT ON COLUMN a2a_tasks.task_id IS
    'A2A wire taskId. publisher 발급, idempotency dedup key.';

COMMENT ON TABLE a2a_task_status_updates IS
    'A2A Task 의 state transition 로그 (immutable). Task 에 containment 종속.';
COMMENT ON COLUMN a2a_task_status_updates.a2a_task_id IS
    'containment FK to a2a_tasks — task 없이 존재 X.';

COMMENT ON TABLE a2a_task_artifacts IS
    'A2A Task 의 산출물 (immutable). Task 에 containment 종속.';
COMMENT ON COLUMN a2a_task_artifacts.a2a_task_id IS
    'containment FK to a2a_tasks — task 없이 존재 X.';

-- ─────────────────────────────────────────────────────────────────────────────
-- 도메인 산출물
-- ─────────────────────────────────────────────────────────────────────────────

COMMENT ON TABLE issues IS
    '외부 이슈 트래커 mirror (Epic / Story / Task type). assignment 진행 '
    '중 발생한 외부 이슈는 assignment_id 로 ref backlink.';
COMMENT ON COLUMN issues.assignment_id IS
    'ref backlink to assignments — 어느 도메인 work item 에서 비롯됐는지 '
    '추적용. NULL 허용. SET NULL on delete.';

COMMENT ON TABLE wiki_pages IS
    '위키 문서 mirror (PRD / ADR / business_rule 등, page_type 으로 분류). '
    'assignment 발이면 assignment_id 로 ref backlink.';
COMMENT ON COLUMN wiki_pages.assignment_id IS
    'ref backlink to assignments — 어느 도메인 work item 에서 비롯됐는지 '
    '추적용. NULL 허용. SET NULL on delete.';
