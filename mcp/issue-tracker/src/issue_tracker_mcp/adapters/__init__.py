"""IssueTracker 어댑터 — ABC + 구현체.

ABC 는 ISP 적용으로 책임별 분할 (`base.py`):
- IssueOps / StatusOps / TypeOps / FieldOps  (4 좁은 ABC)
- IssueTracker  (위 4 의 컴포지트, 어댑터 진입점)

새 backend (Jira / Linear) 추가는 새 패키지 (`adapters/<name>/`) + factory.py 에
1줄 등록 (OCP).
"""

from issue_tracker_mcp.adapters.base import (
    FieldOps,
    IssueOps,
    IssueTracker,
    StatusOps,
    TypeOps,
)
from issue_tracker_mcp.adapters.github import GitHubIssueTrackerAdapter

__all__ = [
    "FieldOps",
    "GitHubIssueTrackerAdapter",
    "IssueOps",
    "IssueTracker",
    "StatusOps",
    "TypeOps",
]
