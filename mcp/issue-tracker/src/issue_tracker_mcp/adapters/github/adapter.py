"""GitHubIssueTrackerAdapter — 4 ops 의 컴포지트 (composition).

각 도메인 ops 는 같은 `_Ctx` 를 공유 (http 클라이언트 + project_id 캐시).
새 backend (Jira / Linear) 추가 시 같은 패턴: 도메인별 ops 클래스 4개 + 컴포지트
1개 + factory.py 에 1줄.
"""

from __future__ import annotations

import httpx

from issue_tracker_mcp.adapters.base import (
    FieldOps,
    IssueOps,
    IssueTracker,
    StatusOps,
    TypeOps,
)
from issue_tracker_mcp.adapters.github._ctx import _Ctx
from issue_tracker_mcp.adapters.github.field import GitHubFieldOps
from issue_tracker_mcp.adapters.github.issue import GitHubIssueOps
from issue_tracker_mcp.adapters.github.status import GitHubStatusOps
from issue_tracker_mcp.adapters.github.type import GitHubTypeOps


class GitHubIssueTrackerAdapter(IssueTracker):
    """GitHub Issues + Projects v2 어댑터.

    호출 진입점:
        adapter = GitHubIssueTrackerAdapter(http, owner=, repo=, project_number=)
        await adapter.issues.create(doc)
        await adapter.statuses.list()

    전제: 대상 Project v2 board 가 owner-level (user / organization) 에 존재.
    field 구조 (Status / Issue Type 등) 는 호출자 (P) 가 `field.list / create`
    로 자율 운영 — 본 어댑터는 lazy 생성하지 않음 (thin bridge 원칙).

    field name 컨벤션:
    - status 도구: board 의 **`Status`** field (GitHub default)
    - type 도구:   board 의 **`Issue Type`** field (`Type` 은 GitHub reserved)
    """

    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        owner: str,
        repo: str,
        project_number: int,
    ) -> None:
        ctx = _Ctx(http, owner=owner, repo=repo, project_number=project_number)
        self._issues = GitHubIssueOps(ctx)
        self._statuses = GitHubStatusOps(ctx)
        self._types = GitHubTypeOps(ctx)
        self._fields = GitHubFieldOps(ctx)

    @property
    def issues(self) -> IssueOps:
        return self._issues

    @property
    def statuses(self) -> StatusOps:
        return self._statuses

    @property
    def types(self) -> TypeOps:
        return self._types

    @property
    def fields(self) -> FieldOps:
        return self._fields


__all__ = ["GitHubIssueTrackerAdapter"]
