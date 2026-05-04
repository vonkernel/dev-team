"""GitHubIssueOps — 이슈 lifecycle (CRUD + close + delete + count + transition)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from dev_team_shared.issue_tracker.schemas.issue import (
    IssueCreate,
    IssueRead,
    IssueUpdate,
)

from issue_tracker_mcp.adapters.base import IssueOps
from issue_tracker_mcp.adapters.github._ctx import _Ctx
from issue_tracker_mcp.adapters.github._field_resolver import (
    require_field_id,
    resolve_field_id,
)
from issue_tracker_mcp.adapters.github._http import (
    GitHubAPIError,
    GitHubGraphQLError,
    graphql,
    rest_request,
)
from issue_tracker_mcp.adapters.github._project_items import (
    add_to_project,
    item_field_values,
    item_id_by_issue_number,
    set_single_select_value,
)


class GitHubIssueOps(IssueOps):
    def __init__(self, ctx: _Ctx) -> None:
        self._ctx = ctx

    # ---- create ----

    async def create(self, doc: IssueCreate) -> IssueRead:
        # 1. REST POST 로 이슈 생성
        rest_payload: dict[str, Any] = {"title": doc.title}
        if doc.body is not None:
            rest_payload["body"] = doc.body
        created = await rest_request(
            self._ctx.http, "POST",
            f"/repos/{self._ctx.owner}/{self._ctx.repo}/issues",
            json=rest_payload,
        )
        issue_node_id = created["node_id"]
        issue_number = created["number"]

        # 2. Project board 에 등록
        item_id = await add_to_project(self._ctx, issue_node_id)

        # 3. type / status 지정 (있으면) — 호출자가 raw id 보냄
        if doc.type_id:
            type_field_id = await require_field_id(self._ctx, "Issue Type")
            await set_single_select_value(
                self._ctx, item_id, type_field_id, doc.type_id,
            )
        if doc.status_id:
            status_field_id = await require_field_id(self._ctx, "Status")
            await set_single_select_value(
                self._ctx, item_id, status_field_id, doc.status_id,
            )

        result = await self.get(str(issue_number))
        if result is None:
            raise RuntimeError(
                f"created issue #{issue_number} not found in subsequent get",
            )
        return result

    # ---- update ----

    async def update(self, ref: str, patch: IssueUpdate) -> IssueRead | None:
        rest_patch: dict[str, Any] = {}
        if patch.title is not None:
            rest_patch["title"] = patch.title
        if patch.body is not None:
            rest_patch["body"] = patch.body

        try:
            if rest_patch:
                await rest_request(
                    self._ctx.http, "PATCH",
                    f"/repos/{self._ctx.owner}/{self._ctx.repo}/issues/{ref}",
                    json=rest_patch,
                )
        except GitHubAPIError as e:
            if e.status_code == 404:
                return None
            raise

        if patch.type_id is not None:
            type_field_id = await require_field_id(self._ctx, "Issue Type")
            item_id = await item_id_by_issue_number(self._ctx, int(ref))
            if item_id is None:
                raise RuntimeError(f"issue #{ref} not on project board")
            await set_single_select_value(
                self._ctx, item_id, type_field_id, patch.type_id,
            )

        return await self.get(ref)

    # ---- read ----

    async def get(self, ref: str) -> IssueRead | None:
        try:
            issue = await rest_request(
                self._ctx.http, "GET",
                f"/repos/{self._ctx.owner}/{self._ctx.repo}/issues/{ref}",
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
        # GitHub REST 는 page 1-indexed. offset → page 변환 (단순 정렬).
        per_page = min(max(limit, 1), 100)
        page = offset // per_page + 1 if offset else 1

        params: dict[str, Any] = {
            "per_page": per_page, "page": page, "state": "all",
        }
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

        if where:
            if "state" in where:
                params["state"] = where["state"]
            if "labels" in where:
                params["labels"] = where["labels"]

        items = await rest_request(
            self._ctx.http, "GET",
            f"/repos/{self._ctx.owner}/{self._ctx.repo}/issues",
            params=params,
        )
        # GitHub REST 의 issues 엔드포인트는 PR 도 포함 — 필터링.
        issues = [it for it in (items or []) if "pull_request" not in it]
        enriched: list[IssueRead] = []
        for it in issues:
            enriched.append(await self._enrich_with_project_fields(it))
        return enriched

    async def count(self, where: dict[str, Any] | None) -> int:
        # GitHub REST 는 정확한 count 미제공 — search API 사용.
        q_parts = [f"repo:{self._ctx.owner}/{self._ctx.repo}", "is:issue"]
        if where:
            state = where.get("state")
            if state == "open":
                q_parts.append("is:open")
            elif state == "closed":
                q_parts.append("is:closed")
        q = " ".join(q_parts)
        result = await rest_request(
            self._ctx.http, "GET", "/search/issues",
            params={"q": q, "per_page": 1},
        )
        return int(result.get("total_count") or 0)

    # ---- close / delete ----

    async def close(self, ref: str) -> bool:
        try:
            await rest_request(
                self._ctx.http, "PATCH",
                f"/repos/{self._ctx.owner}/{self._ctx.repo}/issues/{ref}",
                json={"state": "closed"},
            )
        except GitHubAPIError as e:
            if e.status_code == 404:
                return False
            raise
        return True

    async def delete(self, ref: str) -> bool:
        # REST 에 issue 삭제 없음 — GraphQL deleteIssue (admin 권한 필요).
        try:
            issue = await rest_request(
                self._ctx.http, "GET",
                f"/repos/{self._ctx.owner}/{self._ctx.repo}/issues/{ref}",
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
            await graphql(self._ctx.http, mutation, {"issue_id": node_id})
        except GitHubGraphQLError as e:
            msg = " ".join((err.get("message") or "") for err in e.errors).lower()
            if "does not have permission" in msg or "forbidden" in msg:
                raise RuntimeError(
                    "issue.delete requires repo admin permission "
                    "(use issue.close as alternative)",
                ) from e
            raise
        return True

    # ---- transition ----

    async def transition(self, ref: str, status_id: str) -> None:
        status_field_id = await require_field_id(self._ctx, "Status")
        item_id = await item_id_by_issue_number(self._ctx, int(ref))
        if item_id is None:
            raise RuntimeError(f"issue #{ref} not on project board")
        await set_single_select_value(
            self._ctx, item_id, status_field_id, status_id,
        )

    # ---- internal ----

    async def _enrich_with_project_fields(self, rest_issue: dict[str, Any]) -> IssueRead:
        """REST issue 응답 + Project board 의 status / type 합치기.

        Status / Issue Type field 가 board 에 없으면 해당 필드는 None
        (read 도구는 board setup 미완 상태에서도 호출 가능).
        """
        ref = str(rest_issue["number"])
        status_field_id = await resolve_field_id(self._ctx, "Status")
        type_field_id = await resolve_field_id(self._ctx, "Issue Type")
        status = None
        type_ = None

        if status_field_id or type_field_id:
            item_id = await item_id_by_issue_number(self._ctx, int(ref))
            if item_id is not None:
                status, type_ = await item_field_values(
                    self._ctx, item_id, status_field_id, type_field_id,
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


def _parse_iso(s: str) -> datetime:
    """ISO8601 (Z suffix) → datetime."""
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


__all__ = ["GitHubIssueOps"]
