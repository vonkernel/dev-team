"""Single-select field 의 options 조작 — fetch / add / remove.

GitHub `updateProjectV2Field` mutation 은 options 배열 통째 replace 형태.
add 는 기존 + new, remove 는 기존 - matching id.
"""

from __future__ import annotations

from typing import Any

from issue_tracker_mcp.adapters.github._ctx import _Ctx
from issue_tracker_mcp.adapters.github._http import graphql

_DEFAULT_OPTION_COLOR = "GRAY"


async def fetch_options(ctx: _Ctx, field_id: str) -> list[dict[str, Any]]:
    query = """
    query($field_id: ID!) {
      node(id: $field_id) {
        ... on ProjectV2SingleSelectField {
          options { id name }
        }
      }
    }
    """
    data = await graphql(ctx.http, query, {"field_id": field_id})
    node = data.get("node") or {}
    return list(node.get("options") or [])


async def add_option(ctx: _Ctx, field_id: str, name: str) -> dict[str, Any]:
    """option 추가 (이름 중복 시 기존 항목 반환)."""
    existing = await fetch_options(ctx, field_id)
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

    updated = await _replace_options(ctx, field_id, new_options)
    for opt in updated:
        if opt.get("name") == name:
            return opt
    raise RuntimeError(f"option {name!r} not found after add")


async def remove_option(ctx: _Ctx, field_id: str, option_id: str) -> bool:
    """option 삭제. 미존재 시 False."""
    existing = await fetch_options(ctx, field_id)
    remaining = [opt for opt in existing if opt.get("id") != option_id]
    if len(remaining) == len(existing):
        return False  # 매칭 없음

    new_options = [
        {"name": opt["name"], "color": _DEFAULT_OPTION_COLOR, "description": ""}
        for opt in remaining
    ]
    # GitHub 이 SINGLE_SELECT 의 빈 options 거부 — placeholder 1개로 fallback.
    if not new_options:
        new_options = [
            {"name": "_", "color": _DEFAULT_OPTION_COLOR, "description": ""},
        ]
    await _replace_options(ctx, field_id, new_options)
    return True


async def _replace_options(
    ctx: _Ctx, field_id: str, options: list[dict[str, Any]],
) -> list[dict[str, Any]]:
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
    data = await graphql(ctx.http, mutation, {"field_id": field_id, "options": options})
    return (
        (data.get("updateProjectV2Field") or {}).get("projectV2Field") or {}
    ).get("options") or []


__all__ = ["add_option", "fetch_options", "remove_option"]
