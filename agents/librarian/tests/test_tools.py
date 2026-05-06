"""build_tools 단위 테스트 — DocStoreClient mock 으로 tool ↔ client 메서드 매핑 검증."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from dev_team_shared.doc_store import (
    AgentItemRead,
    AgentSessionRead,
    AgentTaskRead,
    IssueCreate,
    IssueRead,
    WikiPageCreate,
    WikiPageRead,
)

from librarian_agent.tools import build_tools


def _now() -> datetime:
    return datetime.now(UTC)


@pytest.fixture
def mock_client():
    """DocStoreClient 의 모든 메서드를 AsyncMock 으로 stub."""
    client = AsyncMock()
    return client


def test_build_tools_returns_expected_tool_names(mock_client) -> None:
    tools = build_tools(mock_client)
    names = sorted(t.name for t in tools)
    assert names == sorted([
        "wiki_pages_create",
        "wiki_pages_update",
        "wiki_pages_get",
        "wiki_pages_get_by_slug",
        "wiki_pages_list",
        "issues_create",
        "issues_update",
        "issues_get",
        "issues_list",
        "agent_tasks_get",
        "agent_tasks_list",
        "agent_sessions_get",
        "agent_sessions_list",
        "agent_sessions_list_by_task",
        "agent_sessions_find_by_context",
        "agent_items_list",
        "agent_items_list_by_session",
    ])


def _wiki_page_read(slug: str = "prd-x") -> WikiPageRead:
    return WikiPageRead(
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


def _issue_read() -> IssueRead:
    return IssueRead(
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


@pytest.mark.asyncio
async def test_wiki_pages_create_forwards_to_client(mock_client) -> None:
    tools = {t.name: t for t in build_tools(mock_client)}
    expected = _wiki_page_read()
    mock_client.wiki_page_create = AsyncMock(return_value=expected)

    doc = WikiPageCreate(
        agent_task_id=UUID("00000000-0000-0000-0000-000000000099"),
        page_type="prd",
        slug="prd-x",
        title="PRD X",
        content_md="# body",
        author_agent="primary",
    )
    result = await tools["wiki_pages_create"].ainvoke({"doc": doc})
    assert result == expected
    mock_client.wiki_page_create.assert_awaited_once_with(doc)


@pytest.mark.asyncio
async def test_issues_create_forwards_to_client(mock_client) -> None:
    tools = {t.name: t for t in build_tools(mock_client)}
    expected = _issue_read()
    mock_client.issue_create = AsyncMock(return_value=expected)

    doc = IssueCreate(
        agent_task_id=UUID("00000000-0000-0000-0000-000000000099"),
        type="epic",
        title="Epic 1",
        body_md="...",
    )
    result = await tools["issues_create"].ainvoke({"doc": doc})
    assert result == expected
    mock_client.issue_create.assert_awaited_once_with(doc)


@pytest.mark.asyncio
async def test_agent_sessions_find_by_context_forwards(mock_client) -> None:
    tools = {t.name: t for t in build_tools(mock_client)}
    mock_client.agent_session_find_by_context = AsyncMock(return_value=None)

    result = await tools["agent_sessions_find_by_context"].ainvoke({"context_id": "ctx-1"})
    assert result is None
    mock_client.agent_session_find_by_context.assert_awaited_once_with("ctx-1")


@pytest.mark.asyncio
async def test_agent_items_list_by_session_converts_uuid(mock_client) -> None:
    tools = {t.name: t for t in build_tools(mock_client)}
    mock_client.agent_item_list_by_session = AsyncMock(return_value=[])

    sid_str = "00000000-0000-0000-0000-000000000003"
    await tools["agent_items_list_by_session"].ainvoke({"session_id": sid_str})
    mock_client.agent_item_list_by_session.assert_awaited_once_with(UUID(sid_str))


@pytest.mark.asyncio
async def test_wiki_pages_list_forwards_args(mock_client) -> None:
    tools = {t.name: t for t in build_tools(mock_client)}
    mock_client.wiki_page_list = AsyncMock(return_value=[])

    await tools["wiki_pages_list"].ainvoke({
        "where": {"page_type": "prd"},
        "limit": 50,
        "offset": 0,
        "order_by": "created_at DESC",
    })
    mock_client.wiki_page_list.assert_awaited_once_with(
        where={"page_type": "prd"}, limit=50, offset=0, order_by="created_at DESC",
    )
