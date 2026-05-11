"""A2AContextRepository — A2A tier 의 a2a_contexts CRUD."""

from __future__ import annotations

import json
from uuid import UUID

import asyncpg
from dev_team_shared.doc_store.schemas.a2a_context import (
    A2AContextCreate,
    A2AContextRead,
    A2AContextUpdate,
)

from doc_store_mcp.repositories.base import PostgresRepositoryBase


class A2AContextRepository(
    PostgresRepositoryBase[A2AContextCreate, A2AContextUpdate, A2AContextRead],
):
    @property
    def collection_name(self) -> str:
        return "a2a_contexts"

    def _to_read(self, row: asyncpg.Record) -> A2AContextRead:
        d = dict(row)
        if isinstance(d.get("metadata"), str):
            d["metadata"] = json.loads(d["metadata"])
        return A2AContextRead.model_validate(d)

    async def create(self, doc: A2AContextCreate) -> A2AContextRead:
        sql = """
            INSERT INTO a2a_contexts
                (id, initiator_agent, counterpart_agent,
                 parent_session_id, parent_assignment_id,
                 trace_id, topic, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
            RETURNING *
        """
        row = await self._pool.fetchrow(
            sql, doc.id, doc.initiator_agent,
            doc.counterpart_agent, doc.parent_session_id,
            doc.parent_assignment_id, doc.trace_id, doc.topic,
            self._to_jsonb(doc.metadata),
        )
        assert row is not None
        return self._to_read(row)

    async def update(
        self, id: UUID, patch: A2AContextUpdate,
    ) -> A2AContextRead | None:
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
            f"UPDATE a2a_contexts SET {', '.join(set_clauses)} "
            f"WHERE id = ${len(params) + 1} RETURNING *"
        )
        params.append(id)
        row = await self._pool.fetchrow(sql, *params)
        return self._to_read(row) if row else None

    # find_by_context_id 폐기 (#75 PR 4) — context_id 컬럼 자체가 폐기됨.
    # publisher-supplied id 패턴: caller 가 UUID 알면 get(id) 직접 호출.


__all__ = ["A2AContextRepository"]
