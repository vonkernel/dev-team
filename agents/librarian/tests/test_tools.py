"""build_tools 단위 테스트 — DocStoreClient mock 으로 tool ↔ client 메서드 매핑 검증.

분담 모델 정정 (#63 / #64) 후: write 도구 미노출. read 13 op + 조합 1 = 14 op.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from dev_team_shared.doc_store import (
    AgentItemRead,
    AgentSessionRead,
    AgentTaskRead,
    IssueRead,
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
        "wiki_pages_get",
        "wiki_pages_get_by_slug",
        "wiki_pages_list",
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
        "chronicler_log_by_context",
    ])


def test_build_tools_excludes_write_ops(mock_client) -> None:
    """write 도구는 #64 시점에 제거. read 사서 정체성 일관."""
    tools = build_tools(mock_client)
    names = {t.name for t in tools}
    forbidden = {
        "wiki_pages_create", "wiki_pages_update",
        "issues_create", "issues_update",
    }
    assert names.isdisjoint(forbidden)


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


def _agent_session_read(sid: str = "00000000-0000-0000-0000-000000000003") -> AgentSessionRead:
    return AgentSessionRead(
        id=UUID(sid),
        agent_task_id=UUID("00000000-0000-0000-0000-000000000099"),
        initiator="primary",
        counterpart="user-gateway",
        context_id="ctx-1",
        trace_id=None,
        topic=None,
        metadata={},
        started_at=_now(),
        ended_at=None,
    )


def _agent_item_read(iid: str = "00000000-0000-0000-0000-000000000010") -> AgentItemRead:
    return AgentItemRead(
        id=UUID(iid),
        agent_session_id=UUID("00000000-0000-0000-0000-000000000003"),
        prev_item_id=None,
        role="user",
        sender="primary",
        content={"text": "hello"},
        message_id=None,
        metadata={},
        created_at=_now(),
    )


@pytest.mark.asyncio
async def test_wiki_pages_get_forwards_uuid(mock_client) -> None:
    tools = {t.name: t for t in build_tools(mock_client)}
    expected = _wiki_page_read()
    mock_client.wiki_page_get = AsyncMock(return_value=expected)

    pid = "00000000-0000-0000-0000-000000000001"
    result = await tools["wiki_pages_get"].ainvoke({"id": pid})
    assert result == expected
    mock_client.wiki_page_get.assert_awaited_once_with(UUID(pid))


@pytest.mark.asyncio
async def test_issues_list_forwards_args(mock_client) -> None:
    tools = {t.name: t for t in build_tools(mock_client)}
    mock_client.issue_list = AsyncMock(return_value=[_issue_read()])

    await tools["issues_list"].ainvoke({
        "where": {"type": "epic"},
        "limit": 50,
        "offset": 0,
        "order_by": "created_at DESC",
    })
    mock_client.issue_list.assert_awaited_once_with(
        where={"type": "epic"}, limit=50, offset=0, order_by="created_at DESC",
    )


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


# ──────────────────────────────────────────────────────────────────
# chronicler_log_by_context (composite read — #64)
# ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_chronicler_log_by_context_combines_session_and_items(mock_client) -> None:
    """session 존재 → find_by_context + list_by_session 두 번 호출 후 결합."""
    tools = {t.name: t for t in build_tools(mock_client)}
    session = _agent_session_read()
    items = [_agent_item_read()]
    mock_client.agent_session_find_by_context = AsyncMock(return_value=session)
    mock_client.agent_item_list_by_session = AsyncMock(return_value=items)

    result = await tools["chronicler_log_by_context"].ainvoke({"context_id": "ctx-1"})

    assert result.session == session
    assert result.items == items
    mock_client.agent_session_find_by_context.assert_awaited_once_with("ctx-1")
    mock_client.agent_item_list_by_session.assert_awaited_once_with(session.id)


@pytest.mark.asyncio
async def test_chronicler_log_by_context_returns_empty_when_session_missing(mock_client) -> None:
    """session 미존재 → list_by_session 호출 X. items 빈 리스트."""
    tools = {t.name: t for t in build_tools(mock_client)}
    mock_client.agent_session_find_by_context = AsyncMock(return_value=None)
    mock_client.agent_item_list_by_session = AsyncMock(return_value=[])

    result = await tools["chronicler_log_by_context"].ainvoke({"context_id": "ctx-missing"})

    assert result.session is None
    assert result.items == []
    mock_client.agent_session_find_by_context.assert_awaited_once_with("ctx-missing")
    mock_client.agent_item_list_by_session.assert_not_awaited()
