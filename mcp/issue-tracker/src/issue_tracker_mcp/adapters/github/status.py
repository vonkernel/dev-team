"""GitHubStatusOps — board 의 Status field option 메타데이터."""

from __future__ import annotations

from dev_team_shared.issue_tracker.schemas.refs import StatusRef

from issue_tracker_mcp.adapters.base import StatusOps
from issue_tracker_mcp.adapters.github._ctx import _Ctx
from issue_tracker_mcp.adapters.github._field_options import (
    add_option,
    fetch_options,
    remove_option,
)
from issue_tracker_mcp.adapters.github._field_resolver import require_field_id

_STATUS_FIELD_NAME = "Status"  # GitHub default field name


class GitHubStatusOps(StatusOps):
    def __init__(self, ctx: _Ctx) -> None:
        self._ctx = ctx

    async def list(self) -> list[StatusRef]:
        field_id = await require_field_id(self._ctx, _STATUS_FIELD_NAME)
        opts = await fetch_options(self._ctx, field_id)
        return [StatusRef(id=o["id"], name=o["name"]) for o in opts]

    async def create(self, name: str) -> StatusRef:
        field_id = await require_field_id(self._ctx, _STATUS_FIELD_NAME)
        opt = await add_option(self._ctx, field_id, name)
        return StatusRef(id=opt["id"], name=opt["name"])

    async def delete(self, status_id: str) -> bool:
        field_id = await require_field_id(self._ctx, _STATUS_FIELD_NAME)
        return await remove_option(self._ctx, field_id, status_id)


__all__ = ["GitHubStatusOps"]
