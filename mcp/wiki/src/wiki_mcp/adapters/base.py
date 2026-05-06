"""Wiki — 외부 wiki backend 추상.

ISP — 책임별 좁은 ABC + 컴포지트:
- `PageOps` — 페이지 CRUD (6 op)
- `Wiki`    — 위 ops 의 컴포지트 (어댑터 진입점)

호출자 (P 등) 가 좁은 인터페이스에 의존:
    wiki: Wiki = factory(...)
    pages: PageOps = wiki.pages
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from dev_team_shared.wiki.schemas import (
    PageCreate,
    PageRead,
    PageRef,
    PageUpdate,
)


class PageOps(ABC):
    """페이지 lifecycle (6 op)."""

    @abstractmethod
    async def create(self, doc: PageCreate) -> PageRead:
        """페이지 생성. slug 가 이미 있으면 RuntimeError (호출자가 update 하라는 신호)."""

    @abstractmethod
    async def update(self, slug: str, patch: PageUpdate) -> PageRead | None:
        """페이지 갱신. slug 미존재 시 None."""

    @abstractmethod
    async def get(self, slug: str) -> PageRead | None:
        """단건 조회 (front matter parse 포함). slug 미존재 시 None."""

    @abstractmethod
    async def list(self) -> list[PageRef]:
        """모든 페이지 목록 (slug + title 만 — content 본문은 미포함, 가벼움)."""

    @abstractmethod
    async def delete(self, slug: str) -> bool:
        """페이지 삭제. slug 미존재 시 False."""

    @abstractmethod
    async def count(self) -> int:
        """페이지 개수."""


class Wiki(ABC):
    """PageOps 의 컴포지트 — 어댑터 진입점.

    M3 단계엔 page 만 있지만, 향후 (M5+) attachments / categories 등 추가 시
    같은 패턴으로 sub-ops 확장 가능 (ISP).
    """

    @property
    @abstractmethod
    def pages(self) -> PageOps: ...


__all__ = ["PageOps", "Wiki"]
