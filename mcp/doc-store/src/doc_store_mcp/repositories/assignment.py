"""AssignmentRepository — chat tier 의 assignments CRUD."""

from __future__ import annotations

import json
from uuid import UUID

import asyncpg
from dev_team_shared.doc_store.schemas.assignment import (
    AssignmentCreate,
    AssignmentRead,
    AssignmentUpdate,
)

from doc_store_mcp.repositories.base import PostgresRepositoryBase


class AssignmentRepository(
    PostgresRepositoryBase[AssignmentCreate, AssignmentUpdate, AssignmentRead],
):
    @property
    def collection_name(self) -> str:
        return "assignments"

    def _to_read(self, row: asyncpg.Record) -> AssignmentRead:
        d = dict(row)
        if isinstance(d.get("metadata"), str):
            d["metadata"] = json.loads(d["metadata"])
        return AssignmentRead.model_validate(d)

    async def create(self, doc: AssignmentCreate) -> AssignmentRead:
        if doc.id is not None:
            sql = """
                INSERT INTO assignments
                    (id, title, description, status, owner_agent,
                     root_session_id, issue_refs, metadata)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
                RETURNING *
            """
            row = await self._pool.fetchrow(
                sql, doc.id, doc.title, doc.description, doc.status,
                doc.owner_agent, doc.root_session_id, doc.issue_refs,
                self._to_jsonb(doc.metadata),
            )
        else:
            sql = """
                INSERT INTO assignments
                    (title, description, status, owner_agent, root_session_id,
                     issue_refs, metadata)
                VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
                RETURNING *
            """
            row = await self._pool.fetchrow(
                sql, doc.title, doc.description, doc.status, doc.owner_agent,
                doc.root_session_id, doc.issue_refs,
                self._to_jsonb(doc.metadata),
            )
        assert row is not None
        return self._to_read(row)

    async def update(
        self, id: UUID, patch: AssignmentUpdate,
    ) -> AssignmentRead | None:
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
        set_clauses.append("updated_at = NOW()")
        sql = (
            f"UPDATE assignments SET {', '.join(set_clauses)} "
            f"WHERE id = ${len(params) + 1} RETURNING *"
        )
        params.append(id)
        row = await self._pool.fetchrow(sql, *params)
        return self._to_read(row) if row else None

    # ---- 특수 쿼리 ----

    async def list_by_session(
        self, root_session_id: UUID,
    ) -> list[AssignmentRead]:
        rows = await self._pool.fetch(
            "SELECT * FROM assignments WHERE root_session_id = $1 "
            "ORDER BY created_at",
            root_session_id,
        )
        return [self._to_read(r) for r in rows]


__all__ = ["AssignmentRepository"]
