"""IssueTracker 어댑터 팩토리.

config 의 `issue_tracker_type` 으로 구현체 선택. 새 backend 추가 = `_REGISTRY`
에 1줄 + `adapters/<name>.py` 작성 (OCP — 본 함수 본문 수정 불필요).
"""

from __future__ import annotations

from collections.abc import Callable

from issue_tracker_mcp.adapters import GitHubIssueTrackerAdapter, IssueTracker
from issue_tracker_mcp.adapters._github_http import make_client
from issue_tracker_mcp.config import Settings


class UnknownIssueTrackerError(ValueError):
    """config.issue_tracker_type 이 등록되지 않은 값."""


def _build_github(settings: Settings) -> tuple[IssueTracker, Callable[[], object]]:
    if not settings.github_token:
        raise RuntimeError("GITHUB_TOKEN env required for issue_tracker_type=github")
    if not settings.github_target_owner or not settings.github_target_repo:
        raise RuntimeError(
            "GITHUB_TARGET_OWNER + GITHUB_TARGET_REPO env required for github backend",
        )
    if not settings.github_project_number:
        raise RuntimeError("GITHUB_PROJECT_NUMBER env required for github backend")

    http = make_client(settings.github_token)
    adapter = GitHubIssueTrackerAdapter(
        http,
        owner=settings.github_target_owner,
        repo=settings.github_target_repo,
        project_number=settings.github_project_number,
    )
    return adapter, http.aclose


_REGISTRY: dict[str, Callable[[Settings], tuple[IssueTracker, Callable[[], object]]]] = {
    "github": _build_github,
}


def build_tracker(settings: Settings) -> tuple[IssueTracker, Callable[[], object]]:
    """`(adapter, aclose_callable)` 반환.

    aclose 는 lifespan shutdown 에서 호출 — http 클라이언트 자원 해제.
    """
    builder = _REGISTRY.get(settings.issue_tracker_type)
    if builder is None:
        raise UnknownIssueTrackerError(
            f"unknown issue_tracker_type={settings.issue_tracker_type!r} "
            f"(registered: {list(_REGISTRY)})",
        )
    return builder(settings)


__all__ = ["UnknownIssueTrackerError", "build_tracker"]
