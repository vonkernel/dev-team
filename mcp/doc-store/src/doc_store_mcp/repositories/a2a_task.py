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
        sql = """
            INSERT INTO a2a_tasks
                (id, a2a_context_id, state, assignment_id, metadata)
            VALUES ($1, $2, $3, $4, $5::jsonb)
            RETURNING *
        """
        row = await self._pool.fetchrow(
            sql, doc.id, doc.a2a_context_id, doc.state,
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

    # find_by_task_id 폐기 (#75 PR 4) — task_id 컬럼 자체 폐기.
    # publisher-supplied id 패턴: caller 가 UUID 알면 get(id) 직접 호출.


__all__ = ["A2ATaskRepository"]
