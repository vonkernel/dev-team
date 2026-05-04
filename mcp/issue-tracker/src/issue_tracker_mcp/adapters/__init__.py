"""IssueTracker 어댑터 — ABC + 구현체.

새 backend (Jira / Linear 등) 추가는 본 패키지에 새 모듈 작성 + factory.py 에
1줄 등록 (OCP).
"""

from issue_tracker_mcp.adapters.base import IssueTracker
from issue_tracker_mcp.adapters.github import GitHubIssueTrackerAdapter

__all__ = ["GitHubIssueTrackerAdapter", "IssueTracker"]
