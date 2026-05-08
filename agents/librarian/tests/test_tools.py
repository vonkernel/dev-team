"""build_tools 단위 테스트 — DocStoreClient mock 으로 tool ↔ client 메서드 매핑 검증.

#75 재설계 후: chat tier (sessions / chats / assignments) + A2A tier
(a2a_contexts / a2a_messages / a2a_tasks / a2a_task_status_updates /
a2a_task_artifacts) + 도메인 산출물 (issues / wiki_pages) 의 read 도구.
write 도구는 미노출 (#63 분담 모델).
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from dev_team_shared.doc_store import (
    A2AContextRead,
    AssignmentRead,
    IssueRead,
    SessionRead,
    WikiPageRead,
)

from librarian_agent.tools import build_tools


def _now() -> datetime:
    return datetime.now(UTC)


@pytest.fixture
def mock_client():
    """DocStoreClient 의 모든 메서드를 AsyncMock 으로 stub."""
    return AsyncMock()


def test_build_tools_returns_expected_tool_names(mock_client) -> None:
    tools = build_tools(mock_client)
    names = sorted(t.name for t in tools)
    assert names == sorted([
        # 도메인 산출물
        "wiki_pages_get",
        "wiki_pages_get_by_slug",
        "wiki_pages_list",
        "issues_get",
        "issues_list",
        # chat tier
        "assignments_get",
        "assignments_list",
        "assignments_list_by_session",
        "sessions_get",
        "sessions_list",
        "chats_list_by_session",
        # a2a tier
        "a2a_contexts_get",
        "a2a_contexts_list",
        "a2a_contexts_find_by_context_id",
        "a2a_messages_list_by_context",
        "a2a_messages_list_by_task",
        "a2a_tasks_get",
        "a2a_tasks_list",
        "a2a_tasks_find_by_task_id",
        "a2a_task_status_updates_list_by_task",
        "a2a_task_artifacts_list_by_task",
    ])


def test_build_tools_excludes_write_ops(mock_client) -> None:
    """write 도구는 미노출 — read 사서 정체성 (#63)."""
    tools = build_tools(mock_client)
    names = {t.name for t in tools}
    forbidden = {
        "wiki_pages_create", "wiki_pages_update",
        "issues_create", "issues_update",
        "assignments_create", "assignments_update",
        "sessions_create", "sessions_update",
        "a2a_contexts_create", "a2a_messages_create",
        "a2a_tasks_create", "a2a_tasks_update",
    }
    assert names.isdisjoint(forbidden)


# ──────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────


def _wiki_page_read(slug: str = "prd-x") -> WikiPageRead:
    return WikiPageRead(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        assignment_id=UUID("00000000-0000-0000-0000-000000000099"),
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
        assignment_id=UUID("00000000-0000-0000-0000-000000000099"),
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


def _session_read() -> SessionRead:
    return SessionRead(
        id=UUID("00000000-0000-0000-0000-000000000003"),
        agent_endpoint="primary",
        initiator="user",
        counterpart="primary",
        metadata={},
        started_at=_now(),
        ended_at=None,
    )


def _assignment_read() -> AssignmentRead:
    return AssignmentRead(
        id=UUID("00000000-0000-0000-0000-000000000099"),
        title="결제 모듈 추가",
        description=None,
        status="open",
        owner_agent="primary",
        root_session_id=UUID("00000000-0000-0000-0000-000000000003"),
        issue_refs=[],
        metadata={},
        created_at=_now(),
        updated_at=_now(),
    )


def _a2a_context_read() -> A2AContextRead:
    return A2AContextRead(
        id=UUID("00000000-0000-0000-0000-000000000004"),
        context_id="ctx-1",
        initiator_agent="primary",
        counterpart_agent="engineer",
        parent_session_id=None,
        parent_assignment_id=None,
        trace_id=None,
        topic=None,
        metadata={},
        started_at=_now(),
        ended_at=None,
    )


# ──────────────────────────────────────────────────────────────────
# 도메인 산출물 — forwarding
# ──────────────────────────────────────────────────────────────────


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


# ──────────────────────────────────────────────────────────────────
# Chat tier — forwarding
# ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sessions_get_forwards_uuid(mock_client) -> None:
    tools = {t.name: t for t in build_tools(mock_client)}
    expected = _session_read()
    mock_client.session_get = AsyncMock(return_value=expected)

    sid = "00000000-0000-0000-0000-000000000003"
    result = await tools["sessions_get"].ainvoke({"id": sid})
    assert result == expected
    mock_client.session_get.assert_awaited_once_with(UUID(sid))


@pytest.mark.asyncio
async def test_assignments_list_by_session_forwards(mock_client) -> None:
    tools = {t.name: t for t in build_tools(mock_client)}
    mock_client.assignment_list_by_session = AsyncMock(
        return_value=[_assignment_read()],
    )
    sid = "00000000-0000-0000-0000-000000000003"
    await tools["assignments_list_by_session"].ainvoke({"root_session_id": sid})
    mock_client.assignment_list_by_session.assert_awaited_once_with(UUID(sid))


@pytest.mark.asyncio
async def test_chats_list_by_session_forwards(mock_client) -> None:
    tools = {t.name: t for t in build_tools(mock_client)}
    mock_client.chat_list_by_session = AsyncMock(return_value=[])
    sid = "00000000-0000-0000-0000-000000000003"
    await tools["chats_list_by_session"].ainvoke({"session_id": sid})
    mock_client.chat_list_by_session.assert_awaited_once_with(UUID(sid))


# ──────────────────────────────────────────────────────────────────
# A2A tier — forwarding
# ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a2a_contexts_find_by_context_id_forwards(mock_client) -> None:
    tools = {t.name: t for t in build_tools(mock_client)}
    expected = _a2a_context_read()
    mock_client.a2a_context_find_by_context_id = AsyncMock(return_value=expected)

    result = await tools["a2a_contexts_find_by_context_id"].ainvoke(
        {"context_id": "ctx-1"},
    )
    assert result == expected
    mock_client.a2a_context_find_by_context_id.assert_awaited_once_with("ctx-1")


@pytest.mark.asyncio
async def test_a2a_messages_list_by_task_forwards(mock_client) -> None:
    tools = {t.name: t for t in build_tools(mock_client)}
    mock_client.a2a_message_list_by_task = AsyncMock(return_value=[])
    tid = "00000000-0000-0000-0000-000000000005"
    await tools["a2a_messages_list_by_task"].ainvoke({"a2a_task_id": tid})
    mock_client.a2a_message_list_by_task.assert_awaited_once_with(UUID(tid))


@pytest.mark.asyncio
async def test_a2a_tasks_find_by_task_id_forwards(mock_client) -> None:
    tools = {t.name: t for t in build_tools(mock_client)}
    mock_client.a2a_task_find_by_task_id = AsyncMock(return_value=None)
    await tools["a2a_tasks_find_by_task_id"].ainvoke({"task_id": "task-xyz"})
    mock_client.a2a_task_find_by_task_id.assert_awaited_once_with("task-xyz")
