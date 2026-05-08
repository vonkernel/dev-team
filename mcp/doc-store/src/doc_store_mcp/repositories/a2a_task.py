"""A2ATaskRepository — A2A tier 의 a2a_tasks CRUD."""

from __future__ import annotations

import json
from uuid import UUID

import asyncpg

from dev_team_shared.doc_store.schemas.a2a_task import (
    A2ATaskCreate,
    A2ATaskRead,
    A2ATaskUpdate,
)
from doc_store_mcp.repositories.base import PostgresRepositoryBase


class A2ATaskRepository(
    PostgresRepositoryBase[A2ATaskCreate, A2ATaskUpdate, A2ATaskRead],
):
    @property
    def collection_name(self) -> str:
        return "a2a_tasks"

    def _to_read(self, row: asyncpg.Record) -> A2ATaskRead:
        d = dict(row)
        if isinstance(d.get("metadata"), str):
            d["metadata"] = json.loads(d["metadata"])
        return A2ATaskRead.model_validate(d)

    async def create(self, doc: A2ATaskCreate) -> A2ATaskRead:
        if doc.id is not None:
            sql = """
                INSERT INTO a2a_tasks
                    (id, task_id, a2a_context_id, state, assignment_id, metadata)
                VALUES ($1, $2, $3, $4, $5, $6::jsonb)
                RETURNING *
            """
            row = await self._pool.fetchrow(
                sql, doc.id, doc.task_id, doc.a2a_context_id, doc.state,
                doc.assignment_id, self._to_jsonb(doc.metadata),
            )
        else:
            sql = """
                INSERT INTO a2a_tasks
                    (task_id, a2a_context_id, state, assignment_id, metadata)
                VALUES ($1, $2, $3, $4, $5::jsonb)
                RETURNING *
            """
            row = await self._pool.fetchrow(
                sql, doc.task_id, doc.a2a_context_id, doc.state,
                doc.assignment_id, self._to_jsonb(doc.metadata),
            )
        assert row is not None
        return self._to_read(row)

    async def update(
        self, id: UUID, patch: A2ATaskUpdate,
    ) -> A2ATaskRead | None:
        fields = patch.model_dump(exclude_unset=True)
        if not fields:
            return await self.get(id)
        set_clauses: list[str] = []
        params: list[object] = []
        for i, (col, val) in enumerate(fields.items(), start=1):
            if col == "metadata":
                set_clauses.append(f"{col} = ${i}::jsonb")
                params.append(self._to_jsonb(val))
            else:
                set_clauses.append(f"{col} = ${i}")
                params.append(val)
        sql = (
            f"UPDATE a2a_tasks SET {', '.join(set_clauses)} "
            f"WHERE id = ${len(params) + 1} RETURNING *"
        )
        params.append(id)
        row = await self._pool.fetchrow(sql, *params)
        return self._to_read(row) if row else None

    # ---- 특수 쿼리 ----

    async def find_by_task_id(self, task_id: str) -> A2ATaskRead | None:
        """가장 최근 1건 (같은 wire taskId 가 여러 번 등장 가능)."""
        row = await self._pool.fetchrow(
            "SELECT * FROM a2a_tasks WHERE task_id = $1 "
            "ORDER BY submitted_at DESC LIMIT 1",
            task_id,
        )
        return self._to_read(row) if row else None


__all__ = ["A2ATaskRepository"]
