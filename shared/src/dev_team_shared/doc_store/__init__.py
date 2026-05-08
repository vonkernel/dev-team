"""Doc Store MCP SDK — schemas + 도구명 상수 + typed client.

server (mcp/doc-store) 와 client (chronicler / librarian / agents) 모두 본
모듈을 공유 contract 로 import. wire-level 디테일 (도구명 / dict args / JSON
parse) 은 DocStoreClient 안에 격리되어 외부로 새지 않음.

#75 재설계: chat tier (Session / Chat / Assignment) + A2A tier (5 collection)
+ 도메인 산출물 (Issue / WikiPage). 기존 AgentTask / AgentSession / AgentItem
폐기.
"""

from dev_team_shared.doc_store.client import DocStoreClient
from dev_team_shared.doc_store.schemas import (
    A2AContextCreate,
    A2AContextRead,
    A2AContextUpdate,
    A2AMessageCreate,
    A2AMessageRead,
    A2AMessageRole,
    A2ATaskArtifactCreate,
    A2ATaskArtifactRead,
    A2ATaskCreate,
    A2ATaskRead,
    A2ATaskState,
    A2ATaskStatusUpdateCreate,
    A2ATaskStatusUpdateRead,
    A2ATaskUpdate,
    AssignmentCreate,
    AssignmentRead,
    AssignmentStatus,
    AssignmentUpdate,
    ChatCreate,
    ChatRead,
    ChatRole,
    IssueCreate,
    IssueRead,
    IssueUpdate,
    SessionCreate,
    SessionRead,
    SessionUpdate,
    WikiPageCreate,
    WikiPageRead,
    WikiPageUpdate,
)
from dev_team_shared.doc_store.tool_names import (
    A2AContextTools,
    A2AMessageTools,
    A2ATaskArtifactTools,
    A2ATaskStatusUpdateTools,
    A2ATaskTools,
    AssignmentTools,
    ChatTools,
    IssueTools,
    SessionTools,
    WikiPageTools,
)

__all__ = [
    # Chat tier
    "AssignmentCreate",
    "AssignmentRead",
    "AssignmentStatus",
    "AssignmentTools",
    "AssignmentUpdate",
    "ChatCreate",
    "ChatRead",
    "ChatRole",
    "ChatTools",
    "SessionCreate",
    "SessionRead",
    "SessionTools",
    "SessionUpdate",
    # A2A tier
    "A2AContextCreate",
    "A2AContextRead",
    "A2AContextTools",
    "A2AContextUpdate",
    "A2AMessageCreate",
    "A2AMessageRead",
    "A2AMessageRole",
    "A2AMessageTools",
    "A2ATaskArtifactCreate",
    "A2ATaskArtifactRead",
    "A2ATaskArtifactTools",
    "A2ATaskCreate",
    "A2ATaskRead",
    "A2ATaskState",
    "A2ATaskStatusUpdateCreate",
    "A2ATaskStatusUpdateRead",
    "A2ATaskStatusUpdateTools",
    "A2ATaskTools",
    "A2ATaskUpdate",
    # 도메인 산출물
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
