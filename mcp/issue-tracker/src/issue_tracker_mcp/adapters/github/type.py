"""GitHubTypeOps — board 의 Issue Type field option 메타데이터.

`Issue Type` 명을 사용 (GitHub 의 reserved word `Type` 과 충돌 회피 — native
issue types 신기능).
"""

from __future__ import annotations

from dev_team_shared.issue_tracker.schemas.refs import TypeRef

from issue_tracker_mcp.adapters.base import TypeOps
from issue_tracker_mcp.adapters.github._ctx import _Ctx
from issue_tracker_mcp.adapters.github._field_options import (
    add_option,
    fetch_options,
    remove_option,
)
from issue_tracker_mcp.adapters.github._field_resolver import require_field_id

_TYPE_FIELD_NAME = "Issue Type"


class GitHubTypeOps(TypeOps):
    def __init__(self, ctx: _Ctx) -> None:
        self._ctx = ctx

    async def list(self) -> list[TypeRef]:
        field_id = await require_field_id(self._ctx, _TYPE_FIELD_NAME)
        opts = await fetch_options(self._ctx, field_id)
        return [TypeRef(id=o["id"], name=o["name"]) for o in opts]

    async def create(self, name: str) -> TypeRef:
        field_id = await require_field_id(self._ctx, _TYPE_FIELD_NAME)
        opt = await add_option(self._ctx, field_id, name)
        return TypeRef(id=opt["id"], name=opt["name"])

    async def delete(self, type_id: str) -> bool:
        field_id = await require_field_id(self._ctx, _TYPE_FIELD_NAME)
        return await remove_option(self._ctx, field_id, type_id)


__all__ = ["GitHubTypeOps"]
