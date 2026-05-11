"""A2ATaskArtifactRepository — A2A Task 산출물. immutable."""

from __future__ import annotations

import json
from uuid import UUID

import asyncpg
from dev_team_shared.doc_store.schemas.a2a_task_artifact import (
    A2ATaskArtifactCreate,
    A2ATaskArtifactRead,
)
from pydantic import BaseModel

from doc_store_mcp.repositories.base import PostgresRepositoryBase


class A2ATaskArtifactRepository(
    PostgresRepositoryBase[A2ATaskArtifactCreate, BaseModel, A2ATaskArtifactRead],
):
    """immutable. update 미지원."""

    @property
    def collection_name(self) -> str:
        return "a2a_task_artifacts"

    def _to_read(self, row: asyncpg.Record) -> A2ATaskArtifactRead:
        d = dict(row)
        for col in ("parts", "metadata"):
            if isinstance(d.get(col), str):
                d[col] = json.loads(d[col])
        return A2ATaskArtifactRead.model_validate(d)

    async def create(
        self, doc: A2ATaskArtifactCreate,
    ) -> A2ATaskArtifactRead:
        sql = """
            INSERT INTO a2a_task_artifacts
                (id, a2a_task_id, name, parts, metadata)
            VALUES ($1, $2, $3, $4::jsonb, $5::jsonb)
            RETURNING *
        """
        row = await self._pool.fetchrow(
            sql,
            doc.id,
            doc.a2a_task_id,
            doc.name,
            self._to_jsonb(doc.parts),
            self._to_jsonb(doc.metadata),
        )
        assert row is not None
        return self._to_read(row)

    async def update(
        self, id: UUID, patch: BaseModel,  # noqa: ARG002
    ) -> A2ATaskArtifactRead | None:
        raise NotImplementedError("a2a_task_artifacts are immutable")

    # ---- 특수 쿼리 ----

    async def list_by_task(
        self, a2a_task_id: UUID,
    ) -> list[A2ATaskArtifactRead]:
        rows = await self._pool.fetch(
            "SELECT * FROM a2a_task_artifacts WHERE a2a_task_id = $1 "
            "ORDER BY created_at",
            a2a_task_id,
        )
        return [self._to_read(r) for r in rows]


__all__ = ["A2ATaskArtifactRepository"]
