"""Document DB MCP — PostgreSQL JSONB CRUD over streamable HTTP.

`dev_team` DB 의 5 collections (agent_tasks / agent_sessions / agent_items /
issues / wiki_pages) 에 대한 thin CRUD 래퍼. 비즈니스 로직 없음.

자세한 규약은 모듈 루트의 `CLAUDE.md` 참조.
"""

__version__ = "0.1.0"
