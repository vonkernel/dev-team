"""Document DB MCP 의 Pydantic 스키마 — server / client 공유 contract.

server (mcp/doc-store) 와 client (chronicler / 향후 librarian) 모두 본 모듈에서
import. 이전엔 mcp/doc-store 안에 있었으나, contract 는 shared 가 owner.
"""

from dev_team_shared.doc_store.schemas.agent_item import (
    AgentItemCreate,
    AgentItemRead,
)
from dev_team_shared.doc_store.schemas.agent_session import (
    AgentSessionCreate,
    AgentSessionRead,
    AgentSessionUpdate,
)
from dev_team_shared.doc_store.schemas.agent_task import (
    AgentTaskCreate,
    AgentTaskRead,
    AgentTaskUpdate,
)
from dev_team_shared.doc_store.schemas.issue import (
    IssueCreate,
    IssueRead,
    IssueUpdate,
)
from dev_team_shared.doc_store.schemas.wiki_page import (
    WikiPageCreate,
    WikiPageRead,
    WikiPageUpdate,
)

__all__ = [
    "AgentItemCreate",
    "AgentItemRead",
    "AgentSessionCreate",
    "AgentSessionRead",
    "AgentSessionUpdate",
    "AgentTaskCreate",
    "AgentTaskRead",
    "AgentTaskUpdate",
    "IssueCreate",
    "IssueRead",
    "IssueUpdate",
    "WikiPageCreate",
    "WikiPageRead",
    "WikiPageUpdate",
]
