"""Doc Store MCP — PostgreSQL CRUD over streamable HTTP.

`dev_team` DB 의 10 collections — chat tier (sessions / chats / assignments) +
A2A tier (a2a_contexts / a2a_messages / a2a_tasks / a2a_task_status_updates /
a2a_task_artifacts) + 도메인 산출물 (issues / wiki_pages) — 에 대한 thin CRUD
래퍼. 비즈니스 로직 없음 (#75 재설계).

자세한 규약은 모듈 루트의 `CLAUDE.md` 참조.
"""

__version__ = "0.1.0"
