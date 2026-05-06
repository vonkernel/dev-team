"""Wiki 어댑터 팩토리 — config 의 wiki_type 으로 구현체 선택 (OCP)."""

from __future__ import annotations

from collections.abc import Callable

from wiki_mcp.adapters import GitHubWikiAdapter, Wiki
from wiki_mcp.config import Settings


class UnknownWikiTypeError(ValueError):
    """config.wiki_type 이 등록되지 않은 값."""


def _build_github(settings: Settings) -> Wiki:
    if not settings.github_token:
        raise RuntimeError("GITHUB_TOKEN env required for wiki_type=github")
    if not settings.github_target_owner or not settings.github_target_repo:
        raise RuntimeError(
            "GITHUB_TARGET_OWNER + GITHUB_TARGET_REPO env required for github backend",
        )
    return GitHubWikiAdapter(
        owner=settings.github_target_owner,
        repo=settings.github_target_repo,
        token=settings.github_token,
    )


_REGISTRY: dict[str, Callable[[Settings], Wiki]] = {
    "github": _build_github,
}


def build_wiki(settings: Settings) -> Wiki:
    builder = _REGISTRY.get(settings.wiki_type)
    if builder is None:
        raise UnknownWikiTypeError(
            f"unknown wiki_type={settings.wiki_type!r} (registered: {list(_REGISTRY)})",
        )
    return builder(settings)


__all__ = ["UnknownWikiTypeError", "build_wiki"]
