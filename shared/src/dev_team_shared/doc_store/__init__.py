"""Document DB MCP SDK — schemas + 도구명 상수 + typed client.

server (mcp/doc-store) 와 client (chronicler / 향후 librarian) 모두 본 모듈을
공유 contract 로 import. wire-level 디테일 (도구명 / dict args / JSON parse) 은
DocStoreClient 안에 격리되어 외부로 새지 않음.
"""

from dev_team_shared.doc_store.client import DocStoreClient
from dev_team_shared.doc_store.schemas import (
    AgentItemCreate,
    AgentItemRead,
    AgentSessionCreate,
    AgentSessionRead,
    AgentSessionUpdate,
    AgentTaskCreate,
    AgentTaskRead,
    AgentTaskUpdate,
    IssueCreate,
    IssueRead,
    IssueUpdate,
    WikiPageCreate,
    WikiPageRead,
    WikiPageUpdate,
)
from dev_team_shared.doc_store.tool_names import (
    AgentItemTools,
    AgentSessionTools,
    AgentTaskTools,
    IssueTools,
    WikiPageTools,
)

__all__ = [
    "AgentItemCreate",
    "AgentItemRead",
    "AgentItemTools",
    "AgentSessionCreate",
    "AgentSessionRead",
    "AgentSessionTools",
    "AgentSessionUpdate",
    "AgentTaskCreate",
    "AgentTaskRead",
    "AgentTaskTools",
    "AgentTaskUpdate",
    "DocStoreClient",
    "IssueCreate",
    "IssueRead",
    "IssueTools",
    "IssueUpdate",
    "WikiPageCreate",
    "WikiPageRead",
    "WikiPageTools",
    "WikiPageUpdate",
]
