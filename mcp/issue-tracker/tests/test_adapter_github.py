"""GitHubIssueTrackerAdapter — mocked httpx 단위 테스트.

respx 로 REST + GraphQL 응답을 stub. 외부 GitHub API 의존 없음.
실 sandbox 검증은 vonkernel/guestbook 통합 테스트에서.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from dev_team_shared.issue_tracker.schemas import (
    IssueCreate,
    IssueUpdate,
)
from issue_tracker_mcp.adapters.github import GitHubIssueTrackerAdapter

PROJECT_ID = "PVT_TEST"
STATUS_FIELD_ID = "PVTSSF_STATUS"
TYPE_FIELD_ID = "PVTSSF_TYPE"

BACKLOG_ID = "opt_backlog"
READY_ID = "opt_ready"
EPIC_ID = "opt_epic"


def _meta_response() -> dict[str, Any]:
    """`_ensure_meta` 의 GraphQL 응답."""
    return {
        "data": {
            "organization": {
                "projectV2": {
                    "id": PROJECT_ID,
                    "fields": {
                        "nodes": [
                            {"id": STATUS_FIELD_ID, "name": "Status"},
                            {"id": TYPE_FIELD_ID, "name": "Type"},
                            {"id": "other", "name": "Priority"},
                        ],
                    },
                },
            },
            "user": None,
        },
    }


@pytest.fixture
def http() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers={"Authorization": "Bearer test", "Accept": "application/vnd.github+json"},
    )


@pytest.fixture
def adapter(http: httpx.AsyncClient) -> GitHubIssueTrackerAdapter:
    return GitHubIssueTrackerAdapter(
        http, owner="acme", repo="repo", project_number=7,
    )


# ----------------------------------------------------------------------
# _ensure_meta
# ----------------------------------------------------------------------


@respx.mock
async def test_ensure_meta_organization_path(
    adapter: GitHubIssueTrackerAdapter,
) -> None:
    respx.post("https://api.github.com/graphql").mock(
        return_value=httpx.Response(200, json=_meta_response()),
    )
    meta = await adapter._ensure_meta()
    assert meta.project_id == PROJECT_ID
    assert meta.status_field_id == STATUS_FIELD_ID
    assert meta.type_field_id == TYPE_FIELD_ID


@respx.mock
async def test_ensure_meta_user_fallback(
    adapter: GitHubIssueTrackerAdapter,
) -> None:
    user_payload = {
        "data": {
            "organization": None,
            "user": _meta_response()["data"]["organization"],
        },
    }
    respx.post("https://api.github.com/graphql").mock(
        return_value=httpx.Response(200, json=user_payload),
    )
    meta = await adapter._ensure_meta()
    assert meta.project_id == PROJECT_ID


@respx.mock
async def test_ensure_meta_missing_field_fails(
    adapter: GitHubIssueTrackerAdapter,
) -> None:
    payload = {
        "data": {
            "organization": {
                "projectV2": {
                    "id": PROJECT_ID,
                    "fields": {
                        "nodes": [{"id": STATUS_FIELD_ID, "name": "Status"}],  # Type 누락
                    },
                },
            },
            "user": None,
        },
    }
    respx.post("https://api.github.com/graphql").mock(
        return_value=httpx.Response(200, json=payload),
    )
    with pytest.raises(RuntimeError, match="missing required single-select fields"):
        await adapter._ensure_meta()


@respx.mock
async def test_ensure_meta_project_not_found(
    adapter: GitHubIssueTrackerAdapter,
) -> None:
    respx.post("https://api.github.com/graphql").mock(
        return_value=httpx.Response(
            200,
            json={"data": {"organization": None, "user": None}},
        ),
    )
    with pytest.raises(RuntimeError, match="Project v2 not found"):
        await adapter._ensure_meta()


# ----------------------------------------------------------------------
# status / type — list / create
# ----------------------------------------------------------------------


@respx.mock
async def test_list_statuses_returns_options_raw(
    adapter: GitHubIssueTrackerAdapter,
) -> None:
    route = respx.post("https://api.github.com/graphql")

    def _resp(request: httpx.Request) -> httpx.Response:
        body = request.read().decode()
        if "projectV2(number" in body:
            return httpx.Response(200, json=_meta_response())
        # _fetch_field_options
        return httpx.Response(
            200,
            json={
                "data": {
                    "node": {
                        "options": [
                            {"id": BACKLOG_ID, "name": "Backlog"},
                            {"id": READY_ID, "name": "Ready"},
                        ],
                    },
                },
            },
        )

    route.side_effect = _resp
    statuses = await adapter.list_statuses()
    names = [s.name for s in statuses]
    assert names == ["Backlog", "Ready"]
    assert statuses[0].id == BACKLOG_ID


@respx.mock
async def test_create_status_idempotent_on_existing_name(
    adapter: GitHubIssueTrackerAdapter,
) -> None:
    """이름이 이미 있으면 update mutation 호출 X, 기존 id 반환."""
    calls: list[str] = []
    route = respx.post("https://api.github.com/graphql")

    def _resp(request: httpx.Request) -> httpx.Response:
        body = request.read().decode()
        calls.append(body)
        if "projectV2(number" in body:
            return httpx.Response(200, json=_meta_response())
        if "options { id name }" in body and "mutation" not in body:
            return httpx.Response(
                200,
                json={
                    "data": {
                        "node": {
                            "options": [{"id": BACKLOG_ID, "name": "Backlog"}],
                        },
                    },
                },
            )
        # update mutation 안 와야 함
        raise AssertionError(f"unexpected mutation call: {body[:200]}")

    route.side_effect = _resp
    ref = await adapter.create_status("Backlog")
    assert ref.id == BACKLOG_ID
    # mutation 으로 update 호출 안 됨 (idempotent)
    assert all("updateProjectV2Field" not in c for c in calls)


# ----------------------------------------------------------------------
# issue CRUD
# ----------------------------------------------------------------------


def _rest_issue(number: int = 42, *, closed: bool = False) -> dict[str, Any]:
    return {
        "number": number,
        "node_id": "I_node_id",
        "title": "hello",
        "body": "body",
        "state": "closed" if closed else "open",
        "created_at": "2026-05-04T00:00:00Z",
        "updated_at": "2026-05-04T01:00:00Z",
    }


@respx.mock
async def test_close_returns_true_on_success(
    adapter: GitHubIssueTrackerAdapter,
) -> None:
    respx.patch(
        "https://api.github.com/repos/acme/repo/issues/42",
    ).mock(return_value=httpx.Response(200, json=_rest_issue(closed=True)))
    assert await adapter.close("42") is True


@respx.mock
async def test_close_returns_false_on_404(
    adapter: GitHubIssueTrackerAdapter,
) -> None:
    respx.patch(
        "https://api.github.com/repos/acme/repo/issues/999",
    ).mock(return_value=httpx.Response(404, json={"message": "not found"}))
    assert await adapter.close("999") is False


@respx.mock
async def test_get_returns_none_on_404(
    adapter: GitHubIssueTrackerAdapter,
) -> None:
    respx.get(
        "https://api.github.com/repos/acme/repo/issues/999",
    ).mock(return_value=httpx.Response(404, json={"message": "not found"}))
    assert await adapter.get("999") is None


@respx.mock
async def test_count_uses_search_api(
    adapter: GitHubIssueTrackerAdapter,
) -> None:
    route = respx.get("https://api.github.com/search/issues").mock(
        return_value=httpx.Response(200, json={"total_count": 17, "items": []}),
    )
    n = await adapter.count(where={"state": "open"})
    assert n == 17
    # 호출 query 검증
    assert route.called
    sent = route.calls[0].request
    assert "is:issue" in sent.url.params["q"]
    assert "is:open" in sent.url.params["q"]


@respx.mock
async def test_update_returns_none_on_404(
    adapter: GitHubIssueTrackerAdapter,
) -> None:
    respx.patch(
        "https://api.github.com/repos/acme/repo/issues/999",
    ).mock(return_value=httpx.Response(404, json={"message": "not found"}))
    result = await adapter.update("999", IssueUpdate(title="x"))
    assert result is None


# ----------------------------------------------------------------------
# IssueCreate doc 직렬화 (id 필드 raw 통신 검증)
# ----------------------------------------------------------------------


def test_issue_create_doc_carries_raw_ids() -> None:
    """status / type enum 박지 않음 — raw id 그대로 통신 (mcp/CLAUDE.md §0)."""
    doc = IssueCreate(
        title="t", body="b", status_id="opt_xxx", type_id="opt_yyy",
    )
    dumped = doc.model_dump(mode="json")
    assert dumped["status_id"] == "opt_xxx"
    assert dumped["type_id"] == "opt_yyy"
    # 정규화 / 매핑 X — 호출자 가 보낸 그대로 유지
