"""GitHubWikiAdapter — PageOps 의 컴포지트.

새 backend (Notion / Confluence) 추가 시 같은 패턴: 도메인별 ops 클래스 + 컴포지트
1개 + factory 1줄.
"""

from __future__ import annotations

from wiki_mcp.adapters.base import PageOps, Wiki
from wiki_mcp.adapters.github._ctx import _Ctx
from wiki_mcp.adapters.github.page import GitHubPageOps


class GitHubWikiAdapter(Wiki):
    """GitHub Wiki (별 git repo) 어댑터.

    호출:
        wiki = GitHubWikiAdapter(owner=, repo=, token=)
        await wiki.pages.create(doc)

    전제: 대상 GitHub repo 가 wiki 활성화 (`Settings → Features → Wikis`).
    빈 wiki 도 첫 page.create 시 자동 init.
    """

    def __init__(
        self,
        *,
        owner: str,
        repo: str,
        token: str,
    ) -> None:
        ctx = _Ctx(owner=owner, repo=repo, token=token)
        self._pages = GitHubPageOps(ctx)

    @property
    def pages(self) -> PageOps:
        return self._pages


__all__ = ["GitHubWikiAdapter"]
