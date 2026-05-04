"""board 의 field name → id 해소 + 모든 field 조회.

여러 ops 가 공유 (StatusOps 가 'Status', TypeOps 가 'Issue Type', FieldOps 가
모든 것). field 의 캐싱은 안 함 (P 가 `field.create / delete` 로 board 구조를
바꿀 수 있어 stale 위험 — 매번 fetch).
"""

from __future__ import annotations

from typing import Any

from issue_tracker_mcp.adapters.github._ctx import _Ctx
from issue_tracker_mcp.adapters.github._http import graphql


async def list_all_fields(ctx: _Ctx) -> list[dict[str, Any]]:
    """board 의 모든 field (모든 dataType). raw GraphQL response nodes."""
    project_id = await ctx.project_id()
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
    data = await graphql(ctx.http, query, {"project_id": project_id})
    nodes = (((data.get("node") or {}).get("fields")) or {}).get("nodes") or []
    return [n for n in nodes if n.get("id")]


async def resolve_field_id(ctx: _Ctx, name: str) -> str | None:
    for n in await list_all_fields(ctx):
        if n.get("name") == name:
            return str(n["id"])
    return None


async def require_field_id(ctx: _Ctx, name: str) -> str:
    fid = await resolve_field_id(ctx, name)
    if fid is None:
        raise RuntimeError(
            f"Project v2 board has no field named {name!r}. "
            f"Call `field.create` to add it before using {name.lower()}.* tools.",
        )
    return fid


__all__ = ["list_all_fields", "require_field_id", "resolve_field_id"]
