"""Primary 의 LangChain tool composition — 4 채널 builder 호출 + 합치기.

각 채널의 tool 정의는 별도 모듈 (SRP):

| 채널 | 모듈 | 책임 |
|---|---|---|
| Doc Store MCP | `doc_store` | Primary 자기 도메인 직접 write / read |
| IssueTracker MCP | `issue_tracker` | 외부 GitHub Issue 동기화 |
| Wiki MCP | `wiki` | 외부 GitHub Wiki 동기화 |
| Librarian A2A | `librarian` | 자연어 정보 검색 / 외부 리소스 조사 위임 |

본 모듈의 책임은 채널 builder 호출 + 합치기 (thin composer). 새 채널 추가 시
새 builder 모듈 + 본 함수에 호출 한 줄 (OCP).
"""

from __future__ import annotations

from dev_team_shared.a2a.client import A2AClient
from dev_team_shared.doc_store import DocStoreClient
from dev_team_shared.event_bus import EventBus
from dev_team_shared.issue_tracker import IssueTrackerClient
from dev_team_shared.wiki import WikiClient
from langchain_core.tools import BaseTool

from primary_agent.tools.doc_store import build_doc_store_tools
from primary_agent.tools.issue_tracker import build_issue_tracker_tools
from primary_agent.tools.librarian import build_librarian_tools
from primary_agent.tools.wiki import build_wiki_tools


def build_tools(
    *,
    doc_store: DocStoreClient,
    event_bus: EventBus,
    issue_tracker: IssueTrackerClient | None = None,
    wiki: WikiClient | None = None,
    librarian: A2AClient | None = None,
) -> list[BaseTool]:
    """4 채널 클라이언트를 받아 LangChain tool 목록 반환.

    `doc_store` 와 `event_bus` 는 필수 (도구가 직접 wire event publish 필요 —
    예: librarian_query 의 a2a.context.end). 나머지 3 채널은 선택, 미주입 시
    해당 채널 도구 미노출.
    """
    tools: list[BaseTool] = []
    tools += build_doc_store_tools(doc_store)
    if issue_tracker is not None:
        tools += build_issue_tracker_tools(issue_tracker)
    if wiki is not None:
        tools += build_wiki_tools(wiki)
    if librarian is not None:
        tools += build_librarian_tools(librarian, event_bus=event_bus)
    return tools


__all__ = ["build_tools"]
