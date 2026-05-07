"""Wiki MCP 채널 LangChain tools — 외부 GitHub Wiki 양방향 동기화."""

from __future__ import annotations

from dev_team_shared.wiki import (
    PageCreate,
    PageRead,
    PageRef,
    PageUpdate,
    WikiClient,
)
from langchain_core.tools import BaseTool, tool


def build_wiki_tools(client: WikiClient) -> list[BaseTool]:
    """Wiki 채널의 4 op — page CRUD."""

    @tool
    async def external_wiki_page_create(doc: PageCreate) -> PageRead:
        """외부 Wiki (GitHub Wiki) 에 페이지 생성. Doc Store 의 wiki_pages 와 sync."""
        return await client.pages.create(doc)

    @tool
    async def external_wiki_page_update(
        slug: str, patch: PageUpdate,
    ) -> PageRead | None:
        """외부 Wiki 페이지 업데이트 (slug)."""
        return await client.pages.update(slug, patch)

    @tool
    async def external_wiki_page_get(slug: str) -> PageRead | None:
        """외부 Wiki 페이지 조회 (slug). 미존재 시 null."""
        return await client.pages.get(slug)

    @tool
    async def external_wiki_page_list() -> list[PageRef]:
        """외부 Wiki 페이지 리스트 (slug + title 등 ref 만). 본문은 get(slug) 으로."""
        return await client.pages.list()

    return [
        external_wiki_page_create,
        external_wiki_page_update,
        external_wiki_page_get,
        external_wiki_page_list,
    ]


__all__ = ["build_wiki_tools"]
