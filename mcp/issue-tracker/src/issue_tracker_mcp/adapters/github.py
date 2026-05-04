"""GitHub Issues + Projects v2 어댑터.

mcp/CLAUDE.md §0 (thin bridge) 준수:
- 호출자가 보낸 raw id (status_id / type_id) 그대로 GraphQL 에 전달
- 도구 응답을 도메인 Pydantic 으로 1회 변환만 (의미적 매핑 X)
- list_* 결과 정규화 X (도구가 부르는 그대로)

전제 조건:
- 대상 Project v2 board 가 owner-level (user / organization) 에 존재

board 의 field 구조 (`Status` / `Issue Type` single-select 등) 는 호출자 (P) 가
`field.list / field.create` 도구로 자율 운영. 본 모듈은 다음 컨벤션 사용:
- status 도구는 board 의 **`Status`** 필드를 봄 (GitHub default 명)
- type 도구는 board 의 **`Issue Type`** 필드를 봄 (GitHub 의 reserved word
  `Type` 회피 — `Type` 은 native issue types 신기능과 충돌해 create 차단됨)

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
from dev_team_shared.issue_tracker.schemas.refs import FieldRef, StatusRef, TypeRef

logger = logging.getLogger(__name__)


_DEFAULT_OPTION_COLOR = "GRAY"

# GitHub GraphQL ProjectV2CustomFieldType — kind 정규화에 사용
_KIND_TO_DATATYPE = {
    "single_select": "SINGLE_SELECT",
    "text": "TEXT",
    "number": "NUMBER",
    "date": "DATE",
    "iteration": "ITERATION",
}
_DATATYPE_TO_KIND = {v: k for k, v in _KIND_TO_DATATYPE.items()}


class GitHubIssueTrackerAdapter(IssueTracker):
    """GitHub Issues + Projects v2 어댑터.

    project_id 만 캐싱. field id 들은 매번 GraphQL fetch (P 가 `field.create`
    로 board 구조를 바꿀 수 있어 캐시가 stale 가능 — 단순화 선택).
    """

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
        self._project_id: str | None = None

    # ------------------------------------------------------------------
    # project_id resolution (board 자체는 안 바뀌므로 영구 캐시)
    # ------------------------------------------------------------------

    async def _ensure_project_id(self) -> str:
        if self._project_id is not None:
            return self._project_id

        # owner 가 user 인지 organization 인지 미상 → 두 path 시도.
        query = """
        query($login: String!, $number: Int!) {
          organization(login: $login) {
            projectV2(number: $number) { id }
          }
          user(login: $login) {
            projectV2(number: $number) { id }
          }
        }
        """
        try:
            data = await graphql(
                self._http, query,
                {"login": self._owner, "number": self._project_number},
            )
        except GitHubGraphQLError as e:
            # organization / user 한 쪽이 NOT_FOUND 인 게 정상 — partial data 사용.
            if e.data:
                data = e.data
            else:
                raise

        project = (data.get("organization") or {}).get("projectV2") or (
            data.get("user") or {}
        ).get("projectV2")
        if project is None:
            raise RuntimeError(
                f"Project v2 not found: owner={self._owner} number={self._project_number}",
            )
        self._project_id = str(project["id"])
        return self._project_id

    async def _list_all_fields(self) -> list[dict[str, Any]]:
        """board 의 모든 field (모든 dataType) 매번 fetch — caching X."""
        project_id = await self._ensure_project_id()
        query = """
        query($project_id: ID!) {
          node(id: $project_id) {
            ... on ProjectV2 {
              fields(first: 50) {
                nodes {
                  ... on ProjectV2Field { id name dataType }
                  ... on ProjectV2SingleSelectField { id name dataType }
                  ... on ProjectV2IterationField { id name dataType }
                }
              }
            }
          }
        }
        """
        data = await graphql(self._http, query, {"project_id": project_id})
        nodes = (((data.get("node") or {}).get("fields")) or {}).get("nodes") or []
        return [n for n in nodes if n.get("id")]

    async def _resolve_field_id(self, name: str) -> str | None:
        """field name → id. 미존재 시 None."""
        for n in await self._list_all_fields():
            if n.get("name") == name:
                return str(n["id"])
        return None

    async def _require_field_id(self, name: str) -> str:
        fid = await self._resolve_field_id(name)
        if fid is None:
            raise RuntimeError(
                f"Project v2 board has no field named {name!r}. "
                f"Call `field.create` to add it before using {name.lower()}.* tools.",
            )
        return fid

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

    async def _remove_field_option(self, field_id: str, option_id: str) -> bool:
        """Single-select field 의 option 삭제. options 배열에서 제외 후 update.
        option 미존재 시 False, 정상 삭제 시 True."""
        existing = await self._fetch_field_options(field_id)
        remaining = [opt for opt in existing if opt.get("id") != option_id]
        if len(remaining) == len(existing):
            return False  # option_id 매칭 없음

        new_options = [
            {"name": opt["name"], "color": _DEFAULT_OPTION_COLOR, "description": ""}
            for opt in remaining
        ]
        # GitHub 이 SINGLE_SELECT 의 빈 options 거부 — 마지막 1개 삭제 시도면 placeholder
        if not new_options:
            new_options = [
                {"name": "_", "color": _DEFAULT_OPTION_COLOR, "description": ""},
            ]

        mutation = """
        mutation($field_id: ID!, $options: [ProjectV2SingleSelectFieldOptionInput!]!) {
          updateProjectV2Field(input: {fieldId: $field_id, singleSelectOptions: $options}) {
            projectV2Field { ... on ProjectV2SingleSelectField { id } }
          }
        }
        """
        await graphql(
            self._http, mutation, {"field_id": field_id, "options": new_options},
        )
        return True

    # ------------------------------------------------------------------
    # status — list / create / transition
    # ------------------------------------------------------------------

    async def list_statuses(self) -> list[StatusRef]:
        field_id = await self._require_field_id("Status")
        opts = await self._fetch_field_options(field_id)
        return [StatusRef(id=o["id"], name=o["name"]) for o in opts]

    async def create_status(self, name: str) -> StatusRef:
        field_id = await self._require_field_id("Status")
        opt = await self._add_field_option(field_id, name)
        return StatusRef(id=opt["id"], name=opt["name"])

    async def delete_status(self, status_id: str) -> bool:
        field_id = await self._require_field_id("Status")
        return await self._remove_field_option(field_id, status_id)

    async def transition(self, ref: str, status_id: str) -> None:
        project_id = await self._ensure_project_id()
        field_id = await self._require_field_id("Status")
        item_id = await self._project_item_id_by_issue_number(int(ref), project_id)
        if item_id is None:
            raise RuntimeError(f"issue #{ref} not on project board")
        await self._set_single_select_value(project_id, item_id, field_id, status_id)

    # ------------------------------------------------------------------
    # type — list / create
    # ------------------------------------------------------------------

    async def list_types(self) -> list[TypeRef]:
        field_id = await self._require_field_id("Issue Type")
        opts = await self._fetch_field_options(field_id)
        return [TypeRef(id=o["id"], name=o["name"]) for o in opts]

    async def create_type(self, name: str) -> TypeRef:
        field_id = await self._require_field_id("Issue Type")
        opt = await self._add_field_option(field_id, name)
        return TypeRef(id=opt["id"], name=opt["name"])

    async def delete_type(self, type_id: str) -> bool:
        field_id = await self._require_field_id("Issue Type")
        return await self._remove_field_option(field_id, type_id)

    # ------------------------------------------------------------------
    # field — board 구조 자체 discover + manage (PM 워크플로우 자율화)
    # ------------------------------------------------------------------

    async def list_fields(self) -> list[FieldRef]:
        nodes = await self._list_all_fields()
        result: list[FieldRef] = []
        for n in nodes:
            datatype = n.get("dataType") or ""
            kind = _DATATYPE_TO_KIND.get(datatype, datatype.lower())
            result.append(FieldRef(id=str(n["id"]), name=str(n.get("name") or ""), kind=kind))
        return result

    async def delete_field(self, field_id: str) -> bool:
        mutation = """
        mutation($field_id: ID!) {
          deleteProjectV2Field(input: {fieldId: $field_id}) { projectV2Field {
            ... on ProjectV2Field { id }
            ... on ProjectV2SingleSelectField { id }
            ... on ProjectV2IterationField { id }
          } }
        }
        """
        try:
            await graphql(self._http, mutation, {"field_id": field_id})
        except GitHubGraphQLError as e:
            msg = " ".join((err.get("message") or "") for err in e.errors).lower()
            if "not found" in msg or "could not resolve" in msg:
                return False
            raise
        return True

    async def create_field(self, name: str, kind: str = "single_select") -> FieldRef:
        datatype = _KIND_TO_DATATYPE.get(kind)
        if datatype is None:
            raise ValueError(
                f"unsupported kind={kind!r} (supported: {list(_KIND_TO_DATATYPE)})",
            )
        # idempotent — 이미 있으면 그대로 반환 (kind 일치 검증까진 안 함, 호출자 책임)
        for f in await self.list_fields():
            if f.name == name:
                return f

        project_id = await self._ensure_project_id()
        # SINGLE_SELECT 는 options 필수 일 수 있음 — 빈 list 시도, 실패 시 default 1개
        variables: dict[str, Any] = {
            "project_id": project_id,
            "name": name,
            "datatype": datatype,
        }
        if datatype == "SINGLE_SELECT":
            variables["options"] = []

        mutation = """
        mutation(
          $project_id: ID!,
          $name: String!,
          $datatype: ProjectV2CustomFieldType!,
          $options: [ProjectV2SingleSelectFieldOptionInput!]
        ) {
          createProjectV2Field(input: {
            projectId: $project_id,
            name: $name,
            dataType: $datatype,
            singleSelectOptions: $options
          }) {
            projectV2Field {
              ... on ProjectV2Field { id name dataType }
              ... on ProjectV2SingleSelectField { id name dataType }
              ... on ProjectV2IterationField { id name dataType }
            }
          }
        }
        """
        try:
            data = await graphql(self._http, mutation, variables)
        except GitHubGraphQLError as e:
            # SINGLE_SELECT 가 빈 options 거부하는 GitHub 버전 대응
            if datatype == "SINGLE_SELECT" and any(
                "option" in (err.get("message") or "").lower() for err in e.errors
            ):
                variables["options"] = [
                    {"name": "_", "color": _DEFAULT_OPTION_COLOR, "description": ""},
                ]
                data = await graphql(self._http, mutation, variables)
            else:
                raise

        node = ((data.get("createProjectV2Field") or {}).get("projectV2Field")) or {}
        if not node.get("id"):
            raise RuntimeError(f"createProjectV2Field returned no id (name={name!r})")
        result_kind = _DATATYPE_TO_KIND.get(node.get("dataType") or "", kind)
        return FieldRef(
            id=str(node["id"]),
            name=str(node.get("name") or name),
            kind=result_kind,
        )

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
        project_id = await self._ensure_project_id()
        item_id = await self._add_to_project(project_id, issue_node_id)

        # 3. type / status 지정 (있으면) — 호출자가 raw id 보냄
        if doc.type_id:
            type_field_id = await self._require_field_id("Issue Type")
            await self._set_single_select_value(
                project_id, item_id, type_field_id, doc.type_id,
            )
        if doc.status_id:
            status_field_id = await self._require_field_id("Status")
            await self._set_single_select_value(
                project_id, item_id, status_field_id, doc.status_id,
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
            project_id = await self._ensure_project_id()
            type_field_id = await self._require_field_id("Issue Type")
            item_id = await self._project_item_id_by_issue_number(int(ref), project_id)
            if item_id is None:
                raise RuntimeError(f"issue #{ref} not on project board")
            await self._set_single_select_value(
                project_id, item_id, type_field_id, patch.type_id,
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

    async def delete(self, ref: str) -> bool:
        # GitHub REST 에 issue 삭제 없음 — GraphQL deleteIssue 사용 (admin 권한 필요).
        # 먼저 REST 로 issue node id 조회.
        try:
            issue = await rest_request(
                self._http,
                "GET",
                f"/repos/{self._owner}/{self._repo}/issues/{ref}",
            )
        except GitHubAPIError as e:
            if e.status_code == 404:
                return False
            raise
        node_id = issue.get("node_id")
        if not node_id:
            return False
        mutation = """
        mutation($issue_id: ID!) {
          deleteIssue(input: {issueId: $issue_id}) { repository { id } }
        }
        """
        try:
            await graphql(self._http, mutation, {"issue_id": node_id})
        except GitHubGraphQLError as e:
            msg = " ".join((err.get("message") or "") for err in e.errors).lower()
            if "does not have permission" in msg or "forbidden" in msg:
                raise RuntimeError(
                    "issue.delete requires repo admin permission "
                    "(use issue.close as alternative)",
                ) from e
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
        """REST issue 응답 + Project board 의 status / type 를 합쳐 IssueRead.

        Status / Type field 가 board 에 없으면 해당 필드는 None 으로 둠
        (fail-fast 안 함 — read 도구는 board setup 미완 상태에서도 호출 가능).
        """
        ref = str(rest_issue["number"])
        project_id = await self._ensure_project_id()
        status_field_id = await self._resolve_field_id("Status")
        type_field_id = await self._resolve_field_id("Issue Type")
        status: StatusRef | None = None
        type_: TypeRef | None = None

        if status_field_id or type_field_id:
            item_id = await self._project_item_id_by_issue_number(int(ref), project_id)
            if item_id is not None:
                status, type_ = await self._fetch_item_field_values(
                    item_id, status_field_id, type_field_id,
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
        status_field_id: str | None,
        type_field_id: str | None,
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
