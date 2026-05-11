"""A2AMessageRepository — A2A tier 의 a2a_messages CRUD. immutable (no update)."""

from __future__ import annotations

import json
from uuid import UUID

import asyncpg
from dev_team_shared.doc_store.schemas.a2a_message import (
    A2AMessageCreate,
    A2AMessageRead,
)
from pydantic import BaseModel

from doc_store_mcp.repositories.base import PostgresRepositoryBase


class A2AMessageRepository(
    PostgresRepositoryBase[A2AMessageCreate, BaseModel, A2AMessageRead],
):
    """a2a_messages 는 immutable. update 미지원."""

    @property
    def collection_name(self) -> str:
        return "a2a_messages"

    def _to_read(self, row: asyncpg.Record) -> A2AMessageRead:
        d = dict(row)
        for col in ("parts", "metadata"):
            if isinstance(d.get(col), str):
                d[col] = json.loads(d[col])
        return A2AMessageRead.model_validate(d)

    async def create(self, doc: A2AMessageCreate) -> A2AMessageRead:
        sql = """
            INSERT INTO a2a_messages
                (id, a2a_context_id, a2a_task_id, role, sender,
                 parts, prev_message_id, metadata)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8::jsonb)
            RETURNING *
        """
        row = await self._pool.fetchrow(
            sql,
            doc.id,
            doc.a2a_context_id,
            doc.a2a_task_id,
            doc.role,
            doc.sender,
            self._to_jsonb(doc.parts),
            doc.prev_message_id,
            self._to_jsonb(doc.metadata),
        )
        assert row is not None
        return self._to_read(row)

    async def update(self, id: UUID, patch: BaseModel) -> A2AMessageRead | None:  # noqa: ARG002
        raise NotImplementedError("a2a_messages are immutable")

    # ---- 특수 쿼리 ----

    async def list_by_context(self, a2a_context_id: UUID) -> list[A2AMessageRead]:
        rows = await self._pool.fetch(
            "SELECT * FROM a2a_messages WHERE a2a_context_id = $1 "
            "ORDER BY created_at",
            a2a_context_id,
        )
        return [self._to_read(r) for r in rows]

    async def list_by_task(self, a2a_task_id: UUID) -> list[A2AMessageRead]:
        rows = await self._pool.fetch(
            "SELECT * FROM a2a_messages WHERE a2a_task_id = $1 "
            "ORDER BY created_at",
            a2a_task_id,
        )
        return [self._to_read(r) for r in rows]


__all__ = ["A2AMessageRepository"]
