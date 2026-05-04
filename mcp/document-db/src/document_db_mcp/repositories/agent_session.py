"""AgentSessionRepository."""

from __future__ import annotations

import json
from uuid import UUID

import asyncpg

from document_db_mcp.repositories.base import AbstractRepository
from document_db_mcp.schemas.agent_session import (
    AgentSessionCreate,
    AgentSessionRead,
    AgentSessionUpdate,
)


class AgentSessionRepository(
    AbstractRepository[AgentSessionCreate, AgentSessionUpdate, AgentSessionRead],
):
    @property
    def table_name(self) -> str:
        return "agent_sessions"

    def _row_to_read(self, row: asyncpg.Record) -> AgentSessionRead:
        d = dict(row)
        if isinstance(d.get("metadata"), str):
            d["metadata"] = json.loads(d["metadata"])
        return AgentSessionRead.model_validate(d)

    async def create(self, doc: AgentSessionCreate) -> AgentSessionRead:
        sql = """
            INSERT INTO agent_sessions
                (agent_task_id, initiator, counterpart, context_id, trace_id, topic, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
            RETURNING *
        """
        row = await self._pool.fetchrow(
            sql,
            doc.agent_task_id,
            doc.initiator,
            doc.counterpart,
            doc.context_id,
            doc.trace_id,
            doc.topic,
            self._to_jsonb(doc.metadata),
        )
        assert row is not None
        return self._row_to_read(row)

    async def update(self, id: UUID, patch: AgentSessionUpdate) -> AgentSessionRead | None:
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
            f"UPDATE agent_sessions SET {', '.join(set_clauses)} "
            f"WHERE id = ${len(params) + 1} RETURNING *"
        )
        params.append(id)
        row = await self._pool.fetchrow(sql, *params)
        return self._row_to_read(row) if row else None

    # ---- 특수 쿼리 ----

    async def list_by_task(self, agent_task_id: UUID) -> list[AgentSessionRead]:
        rows = await self._pool.fetch(
            "SELECT * FROM agent_sessions WHERE agent_task_id = $1 ORDER BY started_at",
            agent_task_id,
        )
        return [self._row_to_read(r) for r in rows]

    async def find_by_context(self, context_id: str) -> AgentSessionRead | None:
        """가장 최근 session 1건 (같은 contextId 가 여러 turn 에 걸칠 수 있음)."""
        row = await self._pool.fetchrow(
            "SELECT * FROM agent_sessions WHERE context_id = $1 "
            "ORDER BY started_at DESC LIMIT 1",
            context_id,
        )
        return self._row_to_read(row) if row else None


__all__ = ["AgentSessionRepository"]
