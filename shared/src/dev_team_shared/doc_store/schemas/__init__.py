"""Doc Store MCP 의 Pydantic 스키마 — server / client 공유 contract.

server (mcp/doc-store) 와 client (chronicler / librarian / agents) 모두 본
모듈에서 import. 이전엔 mcp/doc-store 안에 있었으나, contract 는 shared 가 owner.

#75 재설계: chat tier (Session / Chat / Assignment) + A2A tier (A2AContext /
A2AMessage / A2ATask / A2ATaskStatusUpdate / A2ATaskArtifact) 두 영역 + 도메인
산출물 (Issue / WikiPage). 기존 AgentTask / AgentSession / AgentItem 폐기.
"""

# Chat tier
# A2A tier
from dev_team_shared.doc_store.schemas.a2a_context import (
    A2AContextCreate,
    A2AContextRead,
    A2AContextUpdate,
)
from dev_team_shared.doc_store.schemas.a2a_message import (
    A2AMessageCreate,
    A2AMessageRead,
    A2AMessageRole,
)
from dev_team_shared.doc_store.schemas.a2a_task import (
    A2ATaskCreate,
    A2ATaskRead,
    A2ATaskState,
    A2ATaskUpdate,
)
from dev_team_shared.doc_store.schemas.a2a_task_artifact import (
    A2ATaskArtifactCreate,
    A2ATaskArtifactRead,
)
from dev_team_shared.doc_store.schemas.a2a_task_status_update import (
    A2ATaskStatusUpdateCreate,
    A2ATaskStatusUpdateRead,
)
from dev_team_shared.doc_store.schemas.assignment import (
    AssignmentCreate,
    AssignmentRead,
    AssignmentStatus,
    AssignmentUpdate,
)
from dev_team_shared.doc_store.schemas.chat import (
    ChatCreate,
    ChatRead,
    ChatRole,
)

# 도메인 산출물
from dev_team_shared.doc_store.schemas.issue import (
    IssueCreate,
    IssueRead,
    IssueUpdate,
)
from dev_team_shared.doc_store.schemas.session import (
    SessionCreate,
    SessionRead,
    SessionUpdate,
)
from dev_team_shared.doc_store.schemas.wiki_page import (
    WikiPageCreate,
    WikiPageRead,
    WikiPageUpdate,
)

__all__ = [
    # Chat tier
    "AssignmentCreate",
    "AssignmentRead",
    "AssignmentStatus",
    "AssignmentUpdate",
    "ChatCreate",
    "ChatRead",
    "ChatRole",
    "SessionCreate",
    "SessionRead",
    "SessionUpdate",
    # A2A tier
    "A2AContextCreate",
    "A2AContextRead",
    "A2AContextUpdate",
    "A2AMessageCreate",
    "A2AMessageRead",
    "A2AMessageRole",
    "A2ATaskArtifactCreate",
    "A2ATaskArtifactRead",
    "A2ATaskCreate",
    "A2ATaskRead",
    "A2ATaskState",
    "A2ATaskStatusUpdateCreate",
    "A2ATaskStatusUpdateRead",
    "A2ATaskUpdate",
    # 도메인 산출물
    "IssueCreate",
    "IssueRead",
    "IssueUpdate",
    "WikiPageCreate",
    "WikiPageRead",
    "WikiPageUpdate",
]
