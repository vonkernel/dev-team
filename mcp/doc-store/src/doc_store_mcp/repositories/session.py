"""SessionRepository — chat tier 의 sessions CRUD."""

from __future__ import annotations

import json
from uuid import UUID

import asyncpg
from dev_team_shared.doc_store.schemas.session import (
    SessionCreate,
    SessionRead,
    SessionUpdate,
)

from doc_store_mcp.repositories.base import PostgresRepositoryBase


class SessionRepository(
    PostgresRepositoryBase[SessionCreate, SessionUpdate, SessionRead],
):
    @property
    def collection_name(self) -> str:
        return "sessions"

    def _to_read(self, row: asyncpg.Record) -> SessionRead:
        d = dict(row)
        if isinstance(d.get("metadata"), str):
            d["metadata"] = json.loads(d["metadata"])
        return SessionRead.model_validate(d)

    async def create(self, doc: SessionCreate) -> SessionRead:
        if doc.id is not None:
            sql = """
                INSERT INTO sessions
                    (id, agent_endpoint, initiator, counterpart, metadata)
                VALUES ($1, $2, $3, $4, $5::jsonb)
                RETURNING *
            """
            row = await self._pool.fetchrow(
                sql, doc.id, doc.agent_endpoint, doc.initiator,
                doc.counterpart, self._to_jsonb(doc.metadata),
            )
        else:
            sql = """
                INSERT INTO sessions
                    (agent_endpoint, initiator, counterpart, metadata)
                VALUES ($1, $2, $3, $4::jsonb)
                RETURNING *
            """
            row = await self._pool.fetchrow(
                sql, doc.agent_endpoint, doc.initiator, doc.counterpart,
                self._to_jsonb(doc.metadata),
            )
        assert row is not None
        return self._to_read(row)

    async def update(self, id: UUID, patch: SessionUpdate) -> SessionRead | None:
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
            f"UPDATE sessions SET {', '.join(set_clauses)} "
            f"WHERE id = ${len(params) + 1} RETURNING *"
        )
        params.append(id)
        row = await self._pool.fetchrow(sql, *params)
        return self._to_read(row) if row else None


__all__ = ["SessionRepository"]
