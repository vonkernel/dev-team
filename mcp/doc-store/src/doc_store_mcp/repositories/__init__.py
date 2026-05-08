"""Repository 레이어 — collection 별 CRUD 구현."""

from doc_store_mcp.repositories.a2a_context import A2AContextRepository
from doc_store_mcp.repositories.a2a_message import A2AMessageRepository
from doc_store_mcp.repositories.a2a_task import A2ATaskRepository
from doc_store_mcp.repositories.a2a_task_artifact import A2ATaskArtifactRepository
from doc_store_mcp.repositories.a2a_task_status_update import (
    A2ATaskStatusUpdateRepository,
)
from doc_store_mcp.repositories.assignment import AssignmentRepository
from doc_store_mcp.repositories.base import (
    AbstractRepository,
    ListFilter,
    PostgresRepositoryBase,
)
from doc_store_mcp.repositories.chat import ChatRepository
from doc_store_mcp.repositories.issue import IssueRepository
from doc_store_mcp.repositories.session import SessionRepository
from doc_store_mcp.repositories.wiki_page import WikiPageRepository

__all__ = [
    "A2AContextRepository",
    "A2AMessageRepository",
    "A2ATaskArtifactRepository",
    "A2ATaskRepository",
    "A2ATaskStatusUpdateRepository",
    "AbstractRepository",
    "AssignmentRepository",
    "ChatRepository",
    "IssueRepository",
    "ListFilter",
    "PostgresRepositoryBase",
    "SessionRepository",
    "WikiPageRepository",
]
