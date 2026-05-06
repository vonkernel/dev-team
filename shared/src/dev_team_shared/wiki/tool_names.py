"""Wiki MCP 도구명 상수 — server / client 공유 source of truth."""

from __future__ import annotations

from typing import Final


class PageTools:
    """페이지 CRUD (6 op).

    `page_type` / `structured` 도메인 필드는 PageCreate / PageUpdate / PageRead
    안에 포함되며, front matter 로 인코딩되어 GitHub Wiki 에 영속됨.
    """

    CREATE: Final = "page.create"
    UPDATE: Final = "page.update"
    GET: Final = "page.get"
    LIST: Final = "page.list"
    DELETE: Final = "page.delete"
    COUNT: Final = "page.count"


__all__ = ["PageTools"]
