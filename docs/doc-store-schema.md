# Doc Store Schema (`dev_team` DB)

> **본 문서는 #75 PR 1/3 에서 폐기됨.** 옛 schema (`agent_tasks` /
> `agent_sessions` / `agent_items`) 는 PR 1 의 재설계 (8 collections +
> assignment_id rename) 와 PR 3 의 cleanup 으로 사라짐. 현 schema 정의는
> 다음 참조:

| 정의 | 위치 |
|---|---|
| **컨셉 수준 모델** (chat tier / A2A tier / 도메인 산출물) | [`docs/proposal/knowledge-model.md`](proposal/knowledge-model.md) §4.2 |
| **실제 마이그레이션 (SQL)** | `mcp/doc-store/migrations/` (`001` ~ `006`) |
| **PostgreSQL COMMENT** (컬럼 단위 의도) | migration `006_table_column_comments.sql` — `psql \d+ <table>` 로 확인 |
| **MCP 도구 면 / 6 op 규약** | [`mcp/doc-store/CLAUDE.md`](../mcp/doc-store/CLAUDE.md) |

## 현 collection 10종 요약

### Chat tier (UG↔P/A)
- `sessions` — 한 대화창. 종료 개념 없음
- `chats` — session 안 발화 (immutable)
- `assignments` — chat 중 합의된 도메인 work item

### A2A tier (에이전트 간)
- `a2a_contexts` — 두 에이전트 사이 대화 namespace. 종료는 agent 가 결정
- `a2a_messages` — A2A Message (immutable). trivial 또는 Task.history
- `a2a_tasks` — A2A Task (stateful work)
- `a2a_task_status_updates` — Task state transition 로그 (immutable)
- `a2a_task_artifacts` — Task 산출물 (immutable)

### 도메인 산출물
- `issues` — 외부 이슈 트래커 mirror
- `wiki_pages` — 위키 문서 mirror (PRD / ADR / business_rule 등 `page_type` 으로 분류)

## 관계 모델 — containment vs ref

- **containment** (NOT NULL FK + CASCADE) — 부모 없으면 존재 X:
  `chats.session_id`, `a2a_messages.a2a_context_id`, `a2a_tasks.a2a_context_id`,
  `a2a_task_status_updates.a2a_task_id`, `a2a_task_artifacts.a2a_task_id`
- **ref backlink** (NULL 허용 + SET NULL) — source 추적 link, 종속 X:
  `assignments.root_session_id`, `a2a_contexts.parent_session_id` /
  `parent_assignment_id`, `a2a_messages.a2a_task_id`, `a2a_tasks.assignment_id`,
  `issues.assignment_id`, `wiki_pages.assignment_id`

자세한 의도는 `knowledge-model.md` §4.2 또는 migration 006 의 `COMMENT ON`
참조.
