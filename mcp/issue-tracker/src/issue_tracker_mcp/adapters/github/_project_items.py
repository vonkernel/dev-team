"""Project board item 조작 — issue 의 board 위 표현 (item) 에 대한 CRUD.

issue (REST) ↔ project item (GraphQL) 매핑:
- issue 생성 후 board 등록: addProjectV2ItemById
- single-select field value 설정: updateProjectV2ItemFieldValue
- issue number → item id 검색: items.nodes 순회
- item 의 status / type field value 조회: ProjectV2ItemFieldSingleSelectValue
"""

from __future__ import annotations

from typing import Any

from dev_team_shared.issue_tracker.schemas.refs import StatusRef, TypeRef

from issue_tracker_mcp.adapters.github._ctx import _Ctx
from issue_tracker_mcp.adapters.github._http import graphql


async def add_to_project(ctx: _Ctx, content_node_id: str) -> str:
    """issue node id → project item id."""
    project_id = await ctx.project_id()
    mutation = """
    mutation($project_id: ID!, $content_id: ID!) {
      addProjectV2ItemById(input: {projectId: $project_id, contentId: $content_id}) {
        item { id }
      }
    }
    """
    data = await graphql(
        ctx.http, mutation,
        {"project_id": project_id, "content_id": content_node_id},
    )
    item = ((data.get("addProjectV2ItemById") or {}).get("item")) or {}
    item_id = item.get("id")
    if not item_id:
        raise RuntimeError("addProjectV2ItemById returned no item id")
    return str(item_id)


async def set_single_select_value(
    ctx: _Ctx,
    item_id: str,
    field_id: str,
    option_id: str,
) -> None:
    project_id = await ctx.project_id()
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
        ctx.http, mutation,
        {
            "project_id": project_id,
            "item_id": item_id,
            "field_id": field_id,
            "option_id": option_id,
        },
    )


async def item_id_by_issue_number(ctx: _Ctx, issue_number: int) -> str | None:
    """Project items 순회 — content.number 매칭. M3 단계 board 가 작아 1 page
    로 충분. 대규모 board 면 후속 최적화."""
    project_id = await ctx.project_id()
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
        data = await graphql(ctx.http, query, {"project_id": project_id, "cursor": cursor})
        items = ((data.get("node") or {}).get("items")) or {}
        for n in items.get("nodes") or []:
            content = n.get("content") or {}
            if content.get("number") == issue_number:
                return str(n["id"])
        page = items.get("pageInfo") or {}
        if not page.get("hasNextPage"):
            return None
        cursor = page.get("endCursor")


async def item_field_values(
    ctx: _Ctx,
    item_id: str,
    status_field_id: str | None,
    type_field_id: str | None,
) -> tuple[StatusRef | None, TypeRef | None]:
    """item 의 single-select field 값들 fetch → StatusRef / TypeRef."""
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
    data = await graphql(ctx.http, query, {"item_id": item_id})
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


__all__ = [
    "add_to_project",
    "item_field_values",
    "item_id_by_issue_number",
    "set_single_select_value",
]
