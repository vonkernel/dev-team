"""ChatRepository — chat tier 의 chats CRUD. immutable (no update)."""

from __future__ import annotations

import json
from uuid import UUID

import asyncpg
from pydantic import BaseModel

from dev_team_shared.doc_store.schemas.chat import ChatCreate, ChatRead
from doc_store_mcp.repositories.base import PostgresRepositoryBase


class ChatRepository(
    PostgresRepositoryBase[ChatCreate, BaseModel, ChatRead],
):
    """chats 는 immutable. update 는 미지원 (호출 시 NotImplementedError)."""

    @property
    def collection_name(self) -> str:
        return "chats"

    def _to_read(self, row: asyncpg.Record) -> ChatRead:
        d = dict(row)
        for col in ("content", "metadata"):
            if isinstance(d.get(col), str):
                d[col] = json.loads(d[col])
        return ChatRead.model_validate(d)

    async def create(self, doc: ChatCreate) -> ChatRead:
        sql = """
            INSERT INTO chats
                (id, session_id, prev_chat_id, role, sender, content, message_id, metadata)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8::jsonb)
            RETURNING *
        """
        row = await self._pool.fetchrow(
            sql,
            doc.id,
            doc.session_id,
            doc.prev_chat_id,
            doc.role,
            doc.sender,
            self._to_jsonb(doc.content),
            doc.message_id,
            self._to_jsonb(doc.metadata),
        )
        assert row is not None
        return self._to_read(row)

    async def update(self, id: UUID, patch: BaseModel) -> ChatRead | None:  # noqa: ARG002
        raise NotImplementedError("chats are immutable")

    # ---- 특수 쿼리 ----

    async def list_by_session(self, session_id: UUID) -> list[ChatRead]:
        rows = await self._pool.fetch(
            "SELECT * FROM chats WHERE session_id = $1 ORDER BY created_at",
            session_id,
        )
        return [self._to_read(r) for r in rows]


__all__ = ["ChatRepository"]
