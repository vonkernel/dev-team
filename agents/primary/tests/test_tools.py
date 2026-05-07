"""build_tools 단위 테스트 — 4 채널 클라이언트 mock 으로 tool ↔ client 매핑 검증."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from dev_team_shared.doc_store import (
    IssueCreate as DocIssueCreate,
    IssueRead as DocIssueRead,
    WikiPageCreate as DocWikiPageCreate,
    WikiPageRead as DocWikiPageRead,
)

from primary_agent.tools import build_tools


def _now() -> datetime:
    return datetime.now(UTC)


def _wiki_page_read(slug: str = "prd-x") -> DocWikiPageRead:
    return DocWikiPageRead(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        agent_task_id=UUID("00000000-0000-0000-0000-000000000099"),
        page_type="prd",
        slug=slug,
        title="PRD X",
        content_md="# body",
        status="draft",
        author_agent="primary",
        references_issues=[],
        references_pages=[],
        structured={},
        external_refs={},
        last_synced_at=None,
        metadata={},
        version=1,
        created_at=_now(),
        updated_at=_now(),
    )


def _issue_read() -> DocIssueRead:
    return DocIssueRead(
        id=UUID("00000000-0000-0000-0000-000000000002"),
        agent_task_id=UUID("00000000-0000-0000-0000-000000000099"),
        type="epic",
        title="Epic 1",
        body_md="...",
        status="draft",
        parent_issue_id=None,
        labels=[],
        external_refs={},
        last_synced_at=None,
        metadata={},
        version=1,
        created_at=_now(),
        updated_at=_now(),
    )


@pytest.fixture
def doc_store():
    return AsyncMock()


@pytest.fixture
def issue_tracker():
    """IssueTrackerClient 의 sub-client 4 개 (issues / statuses / types / fields) 를 AsyncMock 으로 stub."""
    client = MagicMock()
    client.issues = AsyncMock()
    client.statuses = AsyncMock()
    client.types = AsyncMock()
    client.fields = AsyncMock()
    return client


@pytest.fixture
def wiki():
    client = MagicMock()
    client.pages = AsyncMock()
    return client


@pytest.fixture
def librarian():
    """A2AClient 는 sync — `send_message` 만 MagicMock."""
    client = MagicMock()
    client.send_message = MagicMock(return_value={"parts": [{"text": "ok"}]})
    return client


# ──────────────────────────────────────────────────────────────────
# 채널 활성 / 비활성에 따른 tool 목록
# ──────────────────────────────────────────────────────────────────


def test_only_doc_store_when_others_off(doc_store) -> None:
    tools = build_tools(
        doc_store=doc_store, issue_tracker=None, wiki=None, librarian=None,
    )
    names = {t.name for t in tools}
    # Doc Store 채널 11 op
    assert "wiki_pages_create" in names
    assert "wiki_pages_update" in names
    assert "wiki_pages_get" in names
    assert "wiki_pages_get_by_slug" in names
    assert "wiki_pages_list" in names
    assert "issues_create" in names
    assert "issues_update" in names
    assert "issues_get" in names
    assert "issues_list" in names
    assert "agent_tasks_get" in names
    assert "agent_tasks_list" in names
    # 다른 채널 미노출
    assert not any(n.startswith("external_") for n in names)
    assert "librarian_query" not in names


def test_all_channels_on(doc_store, issue_tracker, wiki, librarian) -> None:
    tools = build_tools(
        doc_store=doc_store, issue_tracker=issue_tracker, wiki=wiki, librarian=librarian,
    )
    names = {t.name for t in tools}
    # Doc Store
    assert {"wiki_pages_create", "issues_create", "agent_tasks_list"} <= names
    # IssueTracker (외부)
    assert {
        "external_issue_create", "external_issue_update", "external_issue_list",
        "external_status_list", "external_status_create",
        "external_type_list", "external_type_create",
    } <= names
    # Wiki (외부)
    assert {
        "external_wiki_page_create", "external_wiki_page_update",
        "external_wiki_page_get", "external_wiki_page_list",
    } <= names
    # Librarian
    assert "librarian_query" in names


# ──────────────────────────────────────────────────────────────────
# Doc Store 도구 — forwarding
# ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_wiki_pages_create_forwards(doc_store) -> None:
    tools = {t.name: t for t in build_tools(
        doc_store=doc_store, issue_tracker=None, wiki=None, librarian=None,
    )}
    expected = _wiki_page_read()
    doc_store.wiki_page_create = AsyncMock(return_value=expected)

    doc = DocWikiPageCreate(
        agent_task_id=UUID("00000000-0000-0000-0000-000000000099"),
        page_type="prd",
        slug="prd-x",
        title="PRD X",
        content_md="# body",
        author_agent="primary",
    )
    result = await tools["wiki_pages_create"].ainvoke({"doc": doc})
    assert result == expected
    doc_store.wiki_page_create.assert_awaited_once_with(doc)


@pytest.mark.asyncio
async def test_issues_create_forwards(doc_store) -> None:
    tools = {t.name: t for t in build_tools(
        doc_store=doc_store, issue_tracker=None, wiki=None, librarian=None,
    )}
    expected = _issue_read()
    doc_store.issue_create = AsyncMock(return_value=expected)

    doc = DocIssueCreate(
        agent_task_id=UUID("00000000-0000-0000-0000-000000000099"),
        type="epic",
        title="Epic 1",
        body_md="...",
    )
    result = await tools["issues_create"].ainvoke({"doc": doc})
    assert result == expected
    doc_store.issue_create.assert_awaited_once_with(doc)


@pytest.mark.asyncio
async def test_wiki_pages_list_forwards_args(doc_store) -> None:
    tools = {t.name: t for t in build_tools(
        doc_store=doc_store, issue_tracker=None, wiki=None, librarian=None,
    )}
    doc_store.wiki_page_list = AsyncMock(return_value=[])

    await tools["wiki_pages_list"].ainvoke({
        "where": {"page_type": "prd"},
        "limit": 50,
        "offset": 0,
        "order_by": "created_at DESC",
    })
    doc_store.wiki_page_list.assert_awaited_once_with(
        where={"page_type": "prd"}, limit=50, offset=0, order_by="created_at DESC",
    )


# ──────────────────────────────────────────────────────────────────
# IssueTracker 도구 — forwarding (sub-client.method 매핑)
# ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_external_status_list_forwards(doc_store, issue_tracker) -> None:
    tools = {t.name: t for t in build_tools(
        doc_store=doc_store, issue_tracker=issue_tracker, wiki=None, librarian=None,
    )}
    issue_tracker.statuses.list = AsyncMock(return_value=[])
    await tools["external_status_list"].ainvoke({})
    issue_tracker.statuses.list.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_external_status_create_forwards(doc_store, issue_tracker) -> None:
    tools = {t.name: t for t in build_tools(
        doc_store=doc_store, issue_tracker=issue_tracker, wiki=None, librarian=None,
    )}
    from dev_team_shared.issue_tracker import StatusRef
    issue_tracker.statuses.create = AsyncMock(
        return_value=StatusRef(id="s1", name="Security Review"),
    )
    await tools["external_status_create"].ainvoke({"name": "Security Review"})
    issue_tracker.statuses.create.assert_awaited_once_with("Security Review")


# ──────────────────────────────────────────────────────────────────
# Librarian A2A — sync send_message → async wrap (asyncio.to_thread)
# ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_librarian_query_extracts_text(doc_store, librarian) -> None:
    tools = {t.name: t for t in build_tools(
        doc_store=doc_store, issue_tracker=None, wiki=None, librarian=librarian,
    )}
    librarian.send_message = MagicMock(return_value={
        "parts": [{"text": "found 3 wiki pages: ..."}],
    })
    result = await tools["librarian_query"].ainvoke({"query": "wiki_pages 의 PRD list"})
    assert result == "found 3 wiki pages: ..."
    librarian.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_librarian_query_handles_task_artifact_response(doc_store, librarian) -> None:
    tools = {t.name: t for t in build_tools(
        doc_store=doc_store, issue_tracker=None, wiki=None, librarian=librarian,
    )}
    # Task 형태 응답 — artifacts[].parts[].text 추출
    librarian.send_message = MagicMock(return_value={
        "id": "task-1",
        "status": {"state": "TASK_STATE_COMPLETED"},
        "artifacts": [{"parts": [{"text": "결과: ..."}]}],
    })
    result = await tools["librarian_query"].ainvoke({"query": "..."})
    assert result == "결과: ..."


@pytest.mark.asyncio
async def test_librarian_query_returns_no_response_marker_on_empty(doc_store, librarian) -> None:
    tools = {t.name: t for t in build_tools(
        doc_store=doc_store, issue_tracker=None, wiki=None, librarian=librarian,
    )}
    librarian.send_message = MagicMock(return_value={})
    result = await tools["librarian_query"].ainvoke({"query": "..."})
    assert result == "(no response)"
