"""AgentTaskRepository — agent_tasks CRUD."""

from __future__ import annotations

import json
from uuid import UUID

import asyncpg

from document_db_mcp.repositories.base import AbstractRepository
from dev_team_shared.document_db.schemas.agent_task import (
    AgentTaskCreate,
    AgentTaskRead,
    AgentTaskUpdate,
)


class AgentTaskRepository(
    AbstractRepository[AgentTaskCreate, AgentTaskUpdate, AgentTaskRead],
):
    @property
    def table_name(self) -> str:
        return "agent_tasks"

    def _row_to_read(self, row: asyncpg.Record) -> AgentTaskRead:
        d = dict(row)
        # asyncpg 가 jsonb 를 str 로 반환하는 경우 (driver 버전 / type codec 미설정)
        if isinstance(d.get("metadata"), str):
            d["metadata"] = json.loads(d["metadata"])
        return AgentTaskRead.model_validate(d)

    async def create(self, doc: AgentTaskCreate) -> AgentTaskRead:
        sql = """
            INSERT INTO agent_tasks (title, description, status, owner_agent, issue_refs, metadata)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb)
            RETURNING *
        """
        row = await self._pool.fetchrow(
            sql,
            doc.title,
            doc.description,
            doc.status,
            doc.owner_agent,
            doc.issue_refs,
            self._to_jsonb(doc.metadata),
        )
        assert row is not None
        return self._row_to_read(row)

    async def update(self, id: UUID, patch: AgentTaskUpdate) -> AgentTaskRead | None:
        # 명시된 필드만 patch
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
            f"UPDATE agent_tasks SET {', '.join(set_clauses)} "
            f"WHERE id = ${len(params) + 1} RETURNING *"
        )
        params.append(id)
        row = await self._pool.fetchrow(sql, *params)
        return self._row_to_read(row) if row else None


__all__ = ["AgentTaskRepository"]
