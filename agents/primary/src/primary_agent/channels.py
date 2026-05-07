"""Primary 의 4 채널 client 묶음 + factory.

채널 = 외부 시스템에 직접 호출하는 typed client (Doc Store / IssueTracker /
Wiki / Librarian A2A). lifespan 에서 인스턴스화 후 build_tools 에 전달.

cleanup 은 호출자가 넘긴 `AsyncExitStack` 에 등록 — DIP (lifecycle 책임은
호출자, 본 모듈은 인스턴스 생성만).
"""

from __future__ import annotations

from contextlib import AsyncExitStack
from dataclasses import dataclass

from dev_team_shared.a2a.client import A2AClient
from dev_team_shared.doc_store import DocStoreClient
from dev_team_shared.issue_tracker import IssueTrackerClient
from dev_team_shared.mcp_client import StreamableMCPClient
from dev_team_shared.wiki import WikiClient

from primary_agent.settings import Settings


@dataclass(frozen=True, kw_only=True)
class Channels:
    """build_tools 에 그대로 펼쳐 넣을 수 있는 4 채널 client 묶음.

    doc_store 는 필수. 나머지 3 채널은 env 활성 시에만 인스턴스화.
    """

    doc_store: DocStoreClient
    issue_tracker: IssueTrackerClient | None = None
    wiki: WikiClient | None = None
    librarian: A2AClient | None = None


async def build_channels(settings: Settings, stack: AsyncExitStack) -> Channels:
    """4 채널 client 인스턴스화 + cleanup 을 stack 에 등록 후 Channels 반환.

    각 채널의 client 는 인스턴스화 즉시 stack 에 cleanup 콜백 등록되어
    lifespan 종료 시 역순 close.
    """
    doc_store_mcp = await StreamableMCPClient.connect(settings.doc_store_url)
    stack.push_async_callback(doc_store_mcp.aclose)
    doc_store = DocStoreClient(doc_store_mcp)

    issue_tracker: IssueTrackerClient | None = None
    if settings.issue_tracker_url:
        mcp = await StreamableMCPClient.connect(settings.issue_tracker_url)
        stack.push_async_callback(mcp.aclose)
        issue_tracker = IssueTrackerClient(mcp)

    wiki: WikiClient | None = None
    if settings.wiki_url:
        mcp = await StreamableMCPClient.connect(settings.wiki_url)
        stack.push_async_callback(mcp.aclose)
        wiki = WikiClient(mcp)

    librarian: A2AClient | None = None
    if settings.librarian_url:
        librarian = A2AClient(settings.librarian_url)
        stack.callback(librarian.close)  # sync close

    return Channels(
        doc_store=doc_store,
        issue_tracker=issue_tracker,
        wiki=wiki,
        librarian=librarian,
    )


__all__ = ["Channels", "build_channels"]
