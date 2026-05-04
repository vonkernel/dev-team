"""IssueTracker MCP SDK — schemas + 도구명 상수 + typed client.

server (mcp/issue-tracker) / client (P / 향후 다른 에이전트) 모두 본 모듈을
공유 contract 로 import. wire-level 디테일 (도구명 / dict args / JSON parse) 은
IssueTrackerClient 안에 격리되어 외부로 새지 않음.
"""

from dev_team_shared.issue_tracker.client import IssueTrackerClient
from dev_team_shared.issue_tracker.schemas import (
    FieldRef,
    IssueCreate,
    IssueRead,
    IssueUpdate,
    StatusRef,
    TypeRef,
)
from dev_team_shared.issue_tracker.tool_names import (
    FieldTools,
    IssueTools,
    StatusTools,
    TypeTools,
)

__all__ = [
    "FieldRef",
    "FieldTools",
    "IssueCreate",
    "IssueRead",
    "IssueTools",
    "IssueTrackerClient",
    "IssueUpdate",
    "StatusRef",
    "StatusTools",
    "TypeRef",
    "TypeTools",
]
