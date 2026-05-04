"""GitHubFieldOps — board 의 field 자체 (Status / Issue Type / Priority 등).

board setup 자율화. createProjectV2Field 는 SINGLE_SELECT 의 빈 options 거부
하므로 필요 시 placeholder 1개로 fallback.
"""

from __future__ import annotations

from typing import Any

from dev_team_shared.issue_tracker.schemas.refs import FieldRef

from issue_tracker_mcp.adapters.base import FieldOps
from issue_tracker_mcp.adapters.github._ctx import _Ctx
from issue_tracker_mcp.adapters.github._field_resolver import list_all_fields
from issue_tracker_mcp.adapters.github._http import (
    GitHubGraphQLError,
    graphql,
)

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


class GitHubFieldOps(FieldOps):
    def __init__(self, ctx: _Ctx) -> None:
        self._ctx = ctx

    async def list(self) -> list[FieldRef]:
        nodes = await list_all_fields(self._ctx)
        result: list[FieldRef] = []
        for n in nodes:
            datatype = n.get("dataType") or ""
            kind = _DATATYPE_TO_KIND.get(datatype, datatype.lower())
            result.append(
                FieldRef(id=str(n["id"]), name=str(n.get("name") or ""), kind=kind),
            )
        return result

    async def create(self, name: str, kind: str = "single_select") -> FieldRef:
        datatype = _KIND_TO_DATATYPE.get(kind)
        if datatype is None:
            raise ValueError(
                f"unsupported kind={kind!r} (supported: {list(_KIND_TO_DATATYPE)})",
            )
        # idempotent — 이미 있으면 그대로 반환 (kind 일치 검증까진 안 함, 호출자 책임)
        for f in await self.list():
            if f.name == name:
                return f

        project_id = await self._ctx.project_id()
        variables: dict[str, Any] = {
            "project_id": project_id, "name": name, "datatype": datatype,
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
            projectId: $project_id, name: $name, dataType: $datatype,
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
            data = await graphql(self._ctx.http, mutation, variables)
        except GitHubGraphQLError as e:
            # SINGLE_SELECT 가 빈 options 거부하는 GitHub 버전 대응
            if datatype == "SINGLE_SELECT" and any(
                "option" in (err.get("message") or "").lower() for err in e.errors
            ):
                variables["options"] = [
                    {"name": "_", "color": _DEFAULT_OPTION_COLOR, "description": ""},
                ]
                data = await graphql(self._ctx.http, mutation, variables)
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

    async def delete(self, field_id: str) -> bool:
        mutation = """
        mutation($field_id: ID!) {
          deleteProjectV2Field(input: {fieldId: $field_id}) {
            projectV2Field {
              ... on ProjectV2Field { id }
              ... on ProjectV2SingleSelectField { id }
              ... on ProjectV2IterationField { id }
            }
          }
        }
        """
        try:
            await graphql(self._ctx.http, mutation, {"field_id": field_id})
        except GitHubGraphQLError as e:
            msg = " ".join((err.get("message") or "") for err in e.errors).lower()
            if "not found" in msg or "could not resolve" in msg:
                return False
            raise
        return True


__all__ = ["GitHubFieldOps"]
