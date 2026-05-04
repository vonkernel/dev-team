"""GitHub Issues + Projects v2 어댑터.

mcp/CLAUDE.md §0 (thin bridge) 준수:
- 호출자가 보낸 raw id (status_id / type_id) 그대로 GraphQL 에 전달
- 도구 응답을 도메인 Pydantic 으로 1회 변환만 (의미적 매핑 X)
- list_* 결과 정규화 X (도구가 부르는 그대로)

전제 조건:
- 대상 Project v2 board 가 owner-level (user / organization) 에 존재
- Project 에 single-select 필드 "Status" / "Type" 둘 다 존재
  (없으면 부팅 시 fail-fast — P 가 board UI 또는 별 setup 으로 추가)

issue 식별자:
- 외부 노출 ref: issue number (str). REST 호출 / 사용자 표시용.
- 내부: GraphQL node id 도 보유 (Project item 조작에 필요).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx

from issue_tracker_mcp.adapters._github_http import (
    GitHubAPIError,
    GitHubGraphQLError,
    graphql,
    rest_request,
)
from issue_tracker_mcp.adapters.base import IssueTracker
from dev_team_shared.issue_tracker.schemas.issue import IssueCreate, IssueRead, IssueUpdate
from dev_team_shared.issue_tracker.schemas.refs import StatusRef, TypeRef

logger = logging.getLogger(__name__)


_DEFAULT_OPTION_COLOR = "GRAY"


class _ProjectMeta:
    """부팅 시 1회 fetch 후 캐싱되는 Project 메타데이터."""

    def __init__(
        self,
        project_id: str,
        status_field_id: str,
        type_field_id: str,
    ) -> None:
        self.project_id = project_id
        self.status_field_id = status_field_id
        self.type_field_id = type_field_id


class GitHubIssueTrackerAdapter(IssueTracker):
    """GitHub Issues + Projects v2 어댑터."""

    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        owner: str,
        repo: str,
        project_number: int,
    ) -> None:
        self._http = http
        self._owner = owner
        self._repo = repo
        self._project_number = project_number
        self._meta: _ProjectMeta | None = None

    # ------------------------------------------------------------------
    # 메타데이터 부트스트랩
    # ------------------------------------------------------------------

    async def _ensure_meta(self) -> _ProjectMeta:
        if self._meta is not None:
            return self._meta

        # owner 가 user 인지 organization 인지 알 수 없으므로 두 path 시도.
        query = """
        query($login: String!, $number: Int!) {
          organization(login: $login) {
            projectV2(number: $number) {
              id
              fields(first: 50) {
                nodes {
                  ... on ProjectV2SingleSelectField { id name }
                }
              }
            }
          }
          user(login: $login) {
            projectV2(number: $number) {
              id
              fields(first: 50) {
                nodes {
                  ... on ProjectV2SingleSelectField { id name }
                }
              }
            }
          }
        }
        """
        try:
            data = await graphql(
                self._http,
                query,
                {"login": self._owner, "number": self._project_number},
            )
        except GitHubGraphQLError as e:
            # 둘 중 한쪽 (organization or user) 만 매칭되어 다른 쪽이 errors 로
            # 올 수도. partial data 가 있으면 사용.
            data = e.errors[0].get("data") if e.errors else None
            if data is None:
                raise

        project = (data.get("organization") or {}).get("projectV2") or (
            data.get("user") or {}
        ).get("projectV2")
        if project is None:
            raise RuntimeError(
                f"Project v2 not found: owner={self._owner} number={self._project_number}",
            )

        fields_by_name = {
            (n.get("name") or ""): n.get("id")
            for n in (project.get("fields") or {}).get("nodes") or []
            if n.get("id") is not None
        }
        status_field_id = fields_by_name.get("Status")
        type_field_id = fields_by_name.get("Type")
        missing = [
            name
            for name, fid in (("Status", status_field_id), ("Type", type_field_id))
            if fid is None
        ]
        if missing:
            raise RuntimeError(
                f"Project v2 board missing required single-select fields: {missing}. "
                "Add them in the board UI or via separate setup.",
            )

        self._meta = _ProjectMeta(
            project_id=project["id"],
            status_field_id=status_field_id,  # type: ignore[arg-type]
            type_field_id=type_field_id,  # type: ignore[arg-type]
        )
        return self._meta

    async def _fetch_field_options(self, field_id: str) -> list[dict[str, Any]]:
        query = """
        query($field_id: ID!) {
          node(id: $field_id) {
            ... on ProjectV2SingleSelectField {
              options { id name }
            }
          }
        }
        """
        data = await graphql(self._http, query, {"field_id": field_id})
        node = data.get("node") or {}
        return list(node.get("options") or [])

    async def _add_field_option(self, field_id: str, name: str) -> dict[str, Any]:
        """Single-select field 에 option 추가 (이름 중복 시 기존 항목 반환).

        GraphQL `updateProjectV2Field` 는 options 배열 통째로 replace 형태이므로
        기존 options + 새 option 으로 전체 갱신.
        """
        existing = await self._fetch_field_options(field_id)
        for opt in existing:
            if opt.get("name") == name:
                return opt

        new_options = [
            {"name": opt["name"], "color": _DEFAULT_OPTION_COLOR, "description": ""}
            for opt in existing
        ]
        new_options.append(
            {"name": name, "color": _DEFAULT_OPTION_COLOR, "description": ""},
        )

        mutation = """
        mutation($field_id: ID!, $options: [ProjectV2SingleSelectFieldOptionInput!]!) {
          updateProjectV2Field(input: {fieldId: $field_id, singleSelectOptions: $options}) {
            projectV2Field {
              ... on ProjectV2SingleSelectField {
                options { id name }
              }
            }
          }
        }
        """
        data = await graphql(
            self._http,
            mutation,
            {"field_id": field_id, "options": new_options},
        )
        updated = (
            (data.get("updateProjectV2Field") or {}).get("projectV2Field") or {}
        ).get("options") or []
        for opt in updated:
            if opt.get("name") == name:
                return opt
        raise RuntimeError(f"option {name!r} not found after add")

    # ------------------------------------------------------------------
    # status — list / create / transition
    # ------------------------------------------------------------------

    async def list_statuses(self) -> list[StatusRef]:
        meta = await self._ensure_meta()
        opts = await self._fetch_field_options(meta.status_field_id)
        return [StatusRef(id=o["id"], name=o["name"]) for o in opts]

    async def create_status(self, name: str) -> StatusRef:
        meta = await self._ensure_meta()
        opt = await self._add_field_option(meta.status_field_id, name)
        return StatusRef(id=opt["id"], name=opt["name"])

    async def transition(self, ref: str, status_id: str) -> None:
        meta = await self._ensure_meta()
        item_id = await self._project_item_id_by_issue_number(int(ref), meta.project_id)
        if item_id is None:
            raise RuntimeError(f"issue #{ref} not on project board")
        await self._set_single_select_value(
            meta.project_id, item_id, meta.status_field_id, status_id,
        )

    # ------------------------------------------------------------------
    # type — list / create
    # ------------------------------------------------------------------

    async def list_types(self) -> list[TypeRef]:
        meta = await self._ensure_meta()
        opts = await self._fetch_field_options(meta.type_field_id)
        return [TypeRef(id=o["id"], name=o["name"]) for o in opts]

    async def create_type(self, name: str) -> TypeRef:
        meta = await self._ensure_meta()
        opt = await self._add_field_option(meta.type_field_id, name)
        return TypeRef(id=opt["id"], name=opt["name"])

    # ------------------------------------------------------------------
    # issue CRUD
    # ------------------------------------------------------------------

    async def create(self, doc: IssueCreate) -> IssueRead:
        # 1. REST 로 이슈 생성
        rest_payload: dict[str, Any] = {"title": doc.title}
        if doc.body is not None:
            rest_payload["body"] = doc.body
        created = await rest_request(
            self._http,
            "POST",
            f"/repos/{self._owner}/{self._repo}/issues",
            json=rest_payload,
        )
        issue_node_id = created["node_id"]
        issue_number = created["number"]

        # 2. Project board 에 등록
        meta = await self._ensure_meta()
        item_id = await self._add_to_project(meta.project_id, issue_node_id)

        # 3. type / status 지정 (있으면)
        if doc.type_id:
            await self._set_single_select_value(
                meta.project_id, item_id, meta.type_field_id, doc.type_id,
            )
        if doc.status_id:
            await self._set_single_select_value(
                meta.project_id, item_id, meta.status_field_id, doc.status_id,
            )

        # 4. 최종 상태 fetch (status / type 반영된 모습)
        result = await self.get(str(issue_number))
        if result is None:
            raise RuntimeError(f"created issue #{issue_number} not found in subsequent get")
        return result

    async def update(self, ref: str, patch: IssueUpdate) -> IssueRead | None:
        rest_patch: dict[str, Any] = {}
        if patch.title is not None:
            rest_patch["title"] = patch.title
        if patch.body is not None:
            rest_patch["body"] = patch.body

        try:
            if rest_patch:
                await rest_request(
                    self._http,
                    "PATCH",
                    f"/repos/{self._owner}/{self._repo}/issues/{ref}",
                    json=rest_patch,
                )
        except GitHubAPIError as e:
            if e.status_code == 404:
                return None
            raise

        if patch.type_id is not None:
            meta = await self._ensure_meta()
            item_id = await self._project_item_id_by_issue_number(int(ref), meta.project_id)
            if item_id is None:
                raise RuntimeError(f"issue #{ref} not on project board")
            await self._set_single_select_value(
                meta.project_id, item_id, meta.type_field_id, patch.type_id,
            )

        return await self.get(ref)

    async def get(self, ref: str) -> IssueRead | None:
        try:
            issue = await rest_request(
                self._http,
                "GET",
                f"/repos/{self._owner}/{self._repo}/issues/{ref}",
            )
        except GitHubAPIError as e:
            if e.status_code == 404:
                return None
            raise

        return await self._enrich_with_project_fields(issue)

    async def list(
        self,
        where: dict[str, Any] | None,
        limit: int,
        offset: int,
        order_by: str,
    ) -> list[IssueRead]:
        # GitHub REST 는 cursor 기반 page 1-indexed. offset → page 변환.
        # 단순화: limit ≤ 100, offset 은 page 단위 정렬 (offset // limit + 1).
        per_page = min(max(limit, 1), 100)
        page = offset // per_page + 1 if offset else 1

        params: dict[str, Any] = {
            "per_page": per_page,
            "page": page,
            "state": "all",
        }
        # order_by 는 "created_at DESC" 같은 형태. GitHub REST 는 sort + direction 분리.
        if order_by:
            sort, _, direction = order_by.lower().partition(" ")
            if sort in {"created", "created_at"}:
                params["sort"] = "created"
            elif sort in {"updated", "updated_at"}:
                params["sort"] = "updated"
            elif sort == "comments":
                params["sort"] = "comments"
            if direction in {"asc", "desc"}:
                params["direction"] = direction

        # equality filter 매핑 (단순)
        if where:
            if "state" in where:
                params["state"] = where["state"]
            if "labels" in where:
                params["labels"] = where["labels"]

        items = await rest_request(
            self._http,
            "GET",
            f"/repos/{self._owner}/{self._repo}/issues",
            params=params,
        )
        # GitHub REST 의 issues 엔드포인트는 PR 도 포함 — 필터링.
        issues = [it for it in (items or []) if "pull_request" not in it]
        # 한 번씩 enrich (per-issue project field fetch — N+1 비효율, M3 단계 OK)
        enriched: list[IssueRead] = []
        for it in issues:
            enriched.append(await self._enrich_with_project_fields(it))
        return enriched

    async def close(self, ref: str) -> bool:
        try:
            await rest_request(
                self._http,
                "PATCH",
                f"/repos/{self._owner}/{self._repo}/issues/{ref}",
                json={"state": "closed"},
            )
        except GitHubAPIError as e:
            if e.status_code == 404:
                return False
            raise
        return True

    async def count(self, where: dict[str, Any] | None) -> int:
        # GitHub REST 는 정확한 count 미제공 — search API 사용.
        q_parts = [f"repo:{self._owner}/{self._repo}", "is:issue"]
        if where:
            state = where.get("state")
            if state == "open":
                q_parts.append("is:open")
            elif state == "closed":
                q_parts.append("is:closed")
        q = " ".join(q_parts)
        result = await rest_request(
            self._http,
            "GET",
            "/search/issues",
            params={"q": q, "per_page": 1},
        )
        return int(result.get("total_count") or 0)

    # ------------------------------------------------------------------
    # 내부 helper
    # ------------------------------------------------------------------

    async def _add_to_project(self, project_id: str, content_node_id: str) -> str:
        mutation = """
        mutation($project_id: ID!, $content_id: ID!) {
          addProjectV2ItemById(input: {projectId: $project_id, contentId: $content_id}) {
            item { id }
          }
        }
        """
        data = await graphql(
            self._http,
            mutation,
            {"project_id": project_id, "content_id": content_node_id},
        )
        item = ((data.get("addProjectV2ItemById") or {}).get("item")) or {}
        item_id = item.get("id")
        if not item_id:
            raise RuntimeError("addProjectV2ItemById returned no item id")
        return str(item_id)

    async def _set_single_select_value(
        self,
        project_id: str,
        item_id: str,
        field_id: str,
        option_id: str,
    ) -> None:
        mutation = """
        mutation($project_id: ID!, $item_id: ID!, $field_id: ID!, $option_id: String!) {
          updateProjectV2ItemFieldValue(input: {
            projectId: $project_id,
            itemId: $item_id,
            fieldId: $field_id,
            value: { singleSelectOptionId: $option_id }
          }) {
            projectV2Item { id }
          }
        }
        """
        await graphql(
            self._http,
            mutation,
            {
                "project_id": project_id,
                "item_id": item_id,
                "field_id": field_id,
                "option_id": option_id,
            },
        )

    async def _project_item_id_by_issue_number(
        self,
        issue_number: int,
        project_id: str,
    ) -> str | None:
        # Project items 페이지 순회 — content.number 매칭. M3 단계엔 board 가
        # 작아 1 page 로 충분. 이슈가 많아지면 후속 최적화.
        query = """
        query($project_id: ID!, $cursor: String) {
          node(id: $project_id) {
            ... on ProjectV2 {
              items(first: 100, after: $cursor) {
                pageInfo { hasNextPage endCursor }
                nodes {
                  id
                  content { ... on Issue { number } }
                }
              }
            }
          }
        }
        """
        cursor: str | None = None
        while True:
            data = await graphql(
                self._http,
                query,
                {"project_id": project_id, "cursor": cursor},
            )
            items = ((data.get("node") or {}).get("items")) or {}
            for n in items.get("nodes") or []:
                content = n.get("content") or {}
                if content.get("number") == issue_number:
                    return str(n["id"])
            page = items.get("pageInfo") or {}
            if not page.get("hasNextPage"):
                return None
            cursor = page.get("endCursor")

    async def _enrich_with_project_fields(self, rest_issue: dict[str, Any]) -> IssueRead:
        """REST issue 응답 + Project board 의 status / type 를 합쳐 IssueRead."""
        ref = str(rest_issue["number"])
        meta = await self._ensure_meta()
        status: StatusRef | None = None
        type_: TypeRef | None = None

        item_id = await self._project_item_id_by_issue_number(int(ref), meta.project_id)
        if item_id is not None:
            status, type_ = await self._fetch_item_field_values(
                item_id, meta.status_field_id, meta.type_field_id,
            )

        return IssueRead(
            ref=ref,
            title=rest_issue.get("title") or "",
            body=rest_issue.get("body"),
            type=type_,
            status=status,
            closed=rest_issue.get("state") == "closed",
            created_at=_parse_iso(rest_issue["created_at"]),
            updated_at=_parse_iso(rest_issue["updated_at"]),
        )

    async def _fetch_item_field_values(
        self,
        item_id: str,
        status_field_id: str,
        type_field_id: str,
    ) -> tuple[StatusRef | None, TypeRef | None]:
        query = """
        query($item_id: ID!) {
          node(id: $item_id) {
            ... on ProjectV2Item {
              fieldValues(first: 50) {
                nodes {
                  ... on ProjectV2ItemFieldSingleSelectValue {
                    optionId
                    name
                    field {
                      ... on ProjectV2SingleSelectField { id }
                    }
                  }
                }
              }
            }
          }
        }
        """
        data = await graphql(self._http, query, {"item_id": item_id})
        values = (((data.get("node") or {}).get("fieldValues")) or {}).get("nodes") or []
        status: StatusRef | None = None
        type_: TypeRef | None = None
        for v in values:
            field = v.get("field") or {}
            field_id = field.get("id")
            opt_id = v.get("optionId")
            name = v.get("name")
            if not field_id or not opt_id or not name:
                continue
            if field_id == status_field_id:
                status = StatusRef(id=opt_id, name=name)
            elif field_id == type_field_id:
                type_ = TypeRef(id=opt_id, name=name)
        return status, type_


def _parse_iso(s: str) -> datetime:
    """ISO8601 (with Z suffix) → datetime."""
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


__all__ = ["GitHubIssueTrackerAdapter"]
