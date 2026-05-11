"""A2ATaskStatusUpdateRepository — A2A Task state transition 로그. immutable."""

from __future__ import annotations

import json
from uuid import UUID

import asyncpg
from dev_team_shared.doc_store.schemas.a2a_task_status_update import (
    A2ATaskStatusUpdateCreate,
    A2ATaskStatusUpdateRead,
)
from pydantic import BaseModel

from doc_store_mcp.repositories.base import PostgresRepositoryBase


class A2ATaskStatusUpdateRepository(
    PostgresRepositoryBase[
        A2ATaskStatusUpdateCreate, BaseModel, A2ATaskStatusUpdateRead,
    ],
):
    """immutable. update 미지원."""

    @property
    def collection_name(self) -> str:
        return "a2a_task_status_updates"

    def _to_read(self, row: asyncpg.Record) -> A2ATaskStatusUpdateRead:
        d = dict(row)
        if isinstance(d.get("metadata"), str):
            d["metadata"] = json.loads(d["metadata"])
        return A2ATaskStatusUpdateRead.model_validate(d)

    async def create(
        self, doc: A2ATaskStatusUpdateCreate,
    ) -> A2ATaskStatusUpdateRead:
        sql = """
            INSERT INTO a2a_task_status_updates
                (a2a_task_id, state, reason, metadata)
            VALUES ($1, $2, $3, $4::jsonb)
            RETURNING *
        """
        row = await self._pool.fetchrow(
            sql,
            doc.a2a_task_id,
            doc.state,
            doc.reason,
            self._to_jsonb(doc.metadata),
        )
        assert row is not None
        return self._to_read(row)

    async def update(
        self, id: UUID, patch: BaseModel,  # noqa: ARG002
    ) -> A2ATaskStatusUpdateRead | None:
        raise NotImplementedError("a2a_task_status_updates are immutable")

    # ---- 특수 쿼리 ----

    async def list_by_task(
        self, a2a_task_id: UUID,
    ) -> list[A2ATaskStatusUpdateRead]:
        rows = await self._pool.fetch(
            "SELECT * FROM a2a_task_status_updates WHERE a2a_task_id = $1 "
            "ORDER BY transitioned_at",
            a2a_task_id,
        )
        return [self._to_read(r) for r in rows]


__all__ = ["A2ATaskStatusUpdateRepository"]
