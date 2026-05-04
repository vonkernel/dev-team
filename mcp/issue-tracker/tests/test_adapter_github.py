"""GitHubIssueTrackerAdapter — mocked httpx 단위 테스트.

respx 로 REST + GraphQL 응답을 stub. 외부 GitHub API 의존 없음.
실 sandbox 검증은 vonkernel/guestbook 통합 테스트에서.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from dev_team_shared.issue_tracker.schemas import IssueCreate, IssueUpdate
from issue_tracker_mcp.adapters.github import GitHubIssueTrackerAdapter
from issue_tracker_mcp.adapters.github._ctx import _Ctx

PROJECT_ID = "PVT_TEST"
STATUS_FIELD_ID = "PVTSSF_STATUS"
TYPE_FIELD_ID = "PVTSSF_TYPE"

BACKLOG_ID = "opt_backlog"
READY_ID = "opt_ready"


def _project_id_response(*, location: str = "organization") -> dict[str, Any]:
    """`_ensure_project_id` 의 GraphQL 응답."""
    payload = {"data": {"organization": None, "user": None}}
    payload["data"][location] = {"projectV2": {"id": PROJECT_ID}}
    return payload


def _all_fields_response(
    *, with_status: bool = True, with_type: bool = True,
) -> dict[str, Any]:
    """`_list_all_fields` 의 GraphQL 응답."""
    nodes: list[dict[str, Any]] = []
    if with_status:
        nodes.append({"id": STATUS_FIELD_ID, "name": "Status", "dataType": "SINGLE_SELECT"})
    if with_type:
        nodes.append({"id": TYPE_FIELD_ID, "name": "Type", "dataType": "SINGLE_SELECT"})
    nodes.append({"id": "f_priority", "name": "Priority", "dataType": "SINGLE_SELECT"})
    return {"data": {"node": {"fields": {"nodes": nodes}}}}


def _classify_query(body: str) -> str:
    """GraphQL body 의 의도 분류 — fixture _resp dispatcher 용."""
    if "$login" in body or "projectV2(number" in body:
        return "project_id"
    if "fields(first:" in body and "options" not in body:
        return "list_all_fields"
    if "options { id name }" in body and "mutation" not in body:
        return "field_options"
    if "createProjectV2Field" in body:
        return "create_field"
    if "updateProjectV2Field(input:" in body:
        return "update_field_options"
    if "addProjectV2ItemById" in body:
        return "add_item"
    if "updateProjectV2ItemFieldValue" in body:
        return "set_field_value"
    if "items(first:" in body:
        return "list_items"
    if "fieldValues(first:" in body:
        return "item_field_values"
    return "unknown"


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
# project_id resolution
# ----------------------------------------------------------------------


@pytest.fixture
def ctx(http: httpx.AsyncClient) -> _Ctx:
    return _Ctx(http, owner="acme", repo="repo", project_number=7)


@respx.mock
async def test_ctx_project_id_organization_path(ctx: _Ctx) -> None:
    respx.post("https://api.github.com/graphql").mock(
        return_value=httpx.Response(200, json=_project_id_response()),
    )
    pid = await ctx.project_id()
    assert pid == PROJECT_ID
    # cache hit
    pid2 = await ctx.project_id()
    assert pid2 == PROJECT_ID


@respx.mock
async def test_ctx_project_id_user_fallback(ctx: _Ctx) -> None:
    respx.post("https://api.github.com/graphql").mock(
        return_value=httpx.Response(200, json=_project_id_response(location="user")),
    )
    assert await ctx.project_id() == PROJECT_ID


@respx.mock
async def test_ctx_project_id_not_found(ctx: _Ctx) -> None:
    respx.post("https://api.github.com/graphql").mock(
        return_value=httpx.Response(
            200, json={"data": {"organization": None, "user": None}},
        ),
    )
    with pytest.raises(RuntimeError, match="Project v2 not found"):
        await ctx.project_id()


# ----------------------------------------------------------------------
# field — list / create
# ----------------------------------------------------------------------


@respx.mock
async def test_list_fields_returns_all_with_kind(
    adapter: GitHubIssueTrackerAdapter,
) -> None:
    route = respx.post("https://api.github.com/graphql")

    def _resp(request: httpx.Request) -> httpx.Response:
        body = request.read().decode()
        kind = _classify_query(body)
        if kind == "project_id":
            return httpx.Response(200, json=_project_id_response())
        if kind == "list_all_fields":
            return httpx.Response(200, json=_all_fields_response())
        raise AssertionError(f"unexpected: {kind}")

    route.side_effect = _resp
    fields = await adapter.fields.list()
    names_kinds = [(f.name, f.kind) for f in fields]
    assert ("Status", "single_select") in names_kinds
    assert ("Type", "single_select") in names_kinds
    assert ("Priority", "single_select") in names_kinds


@respx.mock
async def test_create_field_idempotent_when_exists(
    adapter: GitHubIssueTrackerAdapter,
) -> None:
    """Type field 가 이미 있으면 createProjectV2Field 호출 안 함."""
    calls: list[str] = []
    route = respx.post("https://api.github.com/graphql")

    def _resp(request: httpx.Request) -> httpx.Response:
        body = request.read().decode()
        calls.append(_classify_query(body))
        kind = _classify_query(body)
        if kind == "project_id":
            return httpx.Response(200, json=_project_id_response())
        if kind == "list_all_fields":
            return httpx.Response(200, json=_all_fields_response())
        raise AssertionError(f"unexpected: {kind}")

    route.side_effect = _resp
    field = await adapter.fields.create("Type", "single_select")
    assert field.name == "Type"
    assert field.id == TYPE_FIELD_ID
    assert "create_field" not in calls


@respx.mock
async def test_create_field_creates_when_missing(
    adapter: GitHubIssueTrackerAdapter,
) -> None:
    route = respx.post("https://api.github.com/graphql")

    def _resp(request: httpx.Request) -> httpx.Response:
        body = request.read().decode()
        kind = _classify_query(body)
        if kind == "project_id":
            return httpx.Response(200, json=_project_id_response())
        if kind == "list_all_fields":
            return httpx.Response(
                200,
                json=_all_fields_response(with_type=False),
            )
        if kind == "create_field":
            return httpx.Response(
                200,
                json={
                    "data": {
                        "createProjectV2Field": {
                            "projectV2Field": {
                                "id": "F_NEW",
                                "name": "Type",
                                "dataType": "SINGLE_SELECT",
                            },
                        },
                    },
                },
            )
        raise AssertionError(f"unexpected: {kind}")

    route.side_effect = _resp
    field = await adapter.fields.create("Type")
    assert field.id == "F_NEW"
    assert field.name == "Type"
    assert field.kind == "single_select"


def test_create_field_rejects_unknown_kind() -> None:
    adapter = GitHubIssueTrackerAdapter(
        httpx.AsyncClient(),
        owner="acme", repo="repo", project_number=1,
    )
    import asyncio
    with pytest.raises(ValueError, match="unsupported kind"):
        asyncio.run(adapter.fields.create("X", kind="bogus"))


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
        kind = _classify_query(body)
        if kind == "project_id":
            return httpx.Response(200, json=_project_id_response())
        if kind == "list_all_fields":
            return httpx.Response(200, json=_all_fields_response())
        if kind == "field_options":
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
        raise AssertionError(f"unexpected: {kind}")

    route.side_effect = _resp
    statuses = await adapter.statuses.list()
    assert [s.name for s in statuses] == ["Backlog", "Ready"]
    assert statuses[0].id == BACKLOG_ID


@respx.mock
async def test_list_statuses_raises_when_field_missing(
    adapter: GitHubIssueTrackerAdapter,
) -> None:
    """Status field 가 board 에 없으면 helpful 에러 (P 가 field.create 하라는 메시지)."""
    route = respx.post("https://api.github.com/graphql")

    def _resp(request: httpx.Request) -> httpx.Response:
        body = request.read().decode()
        kind = _classify_query(body)
        if kind == "project_id":
            return httpx.Response(200, json=_project_id_response())
        if kind == "list_all_fields":
            return httpx.Response(
                200, json=_all_fields_response(with_status=False),
            )
        raise AssertionError(f"unexpected: {kind}")

    route.side_effect = _resp
    with pytest.raises(RuntimeError, match="no field named 'Status'"):
        await adapter.statuses.list()


@respx.mock
async def test_delete_status_removes_option(
    adapter: GitHubIssueTrackerAdapter,
) -> None:
    calls: list[str] = []
    route = respx.post("https://api.github.com/graphql")

    def _resp(request: httpx.Request) -> httpx.Response:
        body = request.read().decode()
        kind = _classify_query(body)
        calls.append(kind)
        if kind == "project_id":
            return httpx.Response(200, json=_project_id_response())
        if kind == "list_all_fields":
            return httpx.Response(200, json=_all_fields_response())
        if kind == "field_options":
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
        if kind == "update_field_options":
            return httpx.Response(
                200,
                json={
                    "data": {
                        "updateProjectV2Field": {
                            "projectV2Field": {"id": STATUS_FIELD_ID},
                        },
                    },
                },
            )
        raise AssertionError(f"unexpected: {kind}")

    route.side_effect = _resp
    assert await adapter.statuses.delete(BACKLOG_ID) is True
    assert "update_field_options" in calls


@respx.mock
async def test_delete_status_returns_false_when_unknown(
    adapter: GitHubIssueTrackerAdapter,
) -> None:
    route = respx.post("https://api.github.com/graphql")

    def _resp(request: httpx.Request) -> httpx.Response:
        body = request.read().decode()
        kind = _classify_query(body)
        if kind == "project_id":
            return httpx.Response(200, json=_project_id_response())
        if kind == "list_all_fields":
            return httpx.Response(200, json=_all_fields_response())
        if kind == "field_options":
            return httpx.Response(
                200,
                json={"data": {"node": {"options": [{"id": BACKLOG_ID, "name": "Backlog"}]}}},
            )
        raise AssertionError(f"unexpected: {kind}")

    route.side_effect = _resp
    assert await adapter.statuses.delete("nope") is False


@respx.mock
async def test_delete_field_calls_graphql_mutation(
    adapter: GitHubIssueTrackerAdapter,
) -> None:
    respx.post("https://api.github.com/graphql").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "deleteProjectV2Field": {
                        "projectV2Field": {"id": "removed"},
                    },
                },
            },
        ),
    )
    assert await adapter.fields.delete("anyid") is True


@respx.mock
async def test_create_status_idempotent_on_existing_name(
    adapter: GitHubIssueTrackerAdapter,
) -> None:
    calls: list[str] = []
    route = respx.post("https://api.github.com/graphql")

    def _resp(request: httpx.Request) -> httpx.Response:
        body = request.read().decode()
        kind = _classify_query(body)
        calls.append(kind)
        if kind == "project_id":
            return httpx.Response(200, json=_project_id_response())
        if kind == "list_all_fields":
            return httpx.Response(200, json=_all_fields_response())
        if kind == "field_options":
            return httpx.Response(
                200,
                json={
                    "data": {
                        "node": {"options": [{"id": BACKLOG_ID, "name": "Backlog"}]},
                    },
                },
            )
        raise AssertionError(f"unexpected mutation: {kind}")

    route.side_effect = _resp
    ref = await adapter.statuses.create("Backlog")
    assert ref.id == BACKLOG_ID
    assert "update_field_options" not in calls  # update mutation 호출 X


# ----------------------------------------------------------------------
# issue CRUD — REST 경로 및 404 처리
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
    assert await adapter.issues.close("42") is True


@respx.mock
async def test_close_returns_false_on_404(
    adapter: GitHubIssueTrackerAdapter,
) -> None:
    respx.patch(
        "https://api.github.com/repos/acme/repo/issues/999",
    ).mock(return_value=httpx.Response(404, json={"message": "not found"}))
    assert await adapter.issues.close("999") is False


@respx.mock
async def test_delete_issue_uses_graphql_mutation(
    adapter: GitHubIssueTrackerAdapter,
) -> None:
    # 1. REST GET 으로 node_id 조회
    respx.get(
        "https://api.github.com/repos/acme/repo/issues/42",
    ).mock(return_value=httpx.Response(200, json=_rest_issue()))
    # 2. GraphQL deleteIssue mutation
    respx.post("https://api.github.com/graphql").mock(
        return_value=httpx.Response(
            200,
            json={"data": {"deleteIssue": {"repository": {"id": "R_x"}}}},
        ),
    )
    assert await adapter.issues.delete("42") is True


@respx.mock
async def test_delete_issue_returns_false_on_404(
    adapter: GitHubIssueTrackerAdapter,
) -> None:
    respx.get(
        "https://api.github.com/repos/acme/repo/issues/999",
    ).mock(return_value=httpx.Response(404, json={"message": "not found"}))
    assert await adapter.issues.delete("999") is False


@respx.mock
async def test_delete_issue_translates_permission_error(
    adapter: GitHubIssueTrackerAdapter,
) -> None:
    """admin 권한 부족 시 helpful RuntimeError."""
    respx.get(
        "https://api.github.com/repos/acme/repo/issues/42",
    ).mock(return_value=httpx.Response(200, json=_rest_issue()))
    respx.post("https://api.github.com/graphql").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": None,
                "errors": [{"message": "viewer does not have permission to delete this issue"}],
            },
        ),
    )
    with pytest.raises(RuntimeError, match="repo admin permission"):
        await adapter.issues.delete("42")


@respx.mock
async def test_get_returns_none_on_404(
    adapter: GitHubIssueTrackerAdapter,
) -> None:
    respx.get(
        "https://api.github.com/repos/acme/repo/issues/999",
    ).mock(return_value=httpx.Response(404, json={"message": "not found"}))
    assert await adapter.issues.get("999") is None


@respx.mock
async def test_count_uses_search_api(
    adapter: GitHubIssueTrackerAdapter,
) -> None:
    route = respx.get("https://api.github.com/search/issues").mock(
        return_value=httpx.Response(200, json={"total_count": 17, "items": []}),
    )
    n = await adapter.issues.count(where={"state": "open"})
    assert n == 17
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
    result = await adapter.issues.update("999", IssueUpdate(title="x"))
    assert result is None


# ----------------------------------------------------------------------
# IssueCreate doc 직렬화 — raw id 통신 검증
# ----------------------------------------------------------------------


def test_issue_create_doc_carries_raw_ids() -> None:
    """status / type enum 박지 않음 — raw id 그대로 통신 (mcp/CLAUDE.md §0)."""
    doc = IssueCreate(
        title="t", body="b", status_id="opt_xxx", type_id="opt_yyy",
    )
    dumped = doc.model_dump(mode="json")
    assert dumped["status_id"] == "opt_xxx"
    assert dumped["type_id"] == "opt_yyy"
