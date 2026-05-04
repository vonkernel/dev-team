"""AgentItemRepository — items 는 immutable. update 는 의도적으로 미지원."""

from __future__ import annotations

import json
from typing import NoReturn
from uuid import UUID

import asyncpg

from document_db_mcp.repositories.base import AbstractRepository
from dev_team_shared.document_db.schemas.agent_item import AgentItemCreate, AgentItemRead


class _ImmutableUpdate:  # placeholder type for ABC contract
    pass


class AgentItemRepository(
    AbstractRepository[AgentItemCreate, _ImmutableUpdate, AgentItemRead],
):
    """대화 메시지 1건. 한 번 쓰면 변경 X (audit / Chronicler 의 영속성).

    update 는 ABC 계약상 시그니처는 있으나 호출 시 RuntimeError. tools 는 노출하지 않음.
    """

    @property
    def table_name(self) -> str:
        return "agent_items"

    def _row_to_read(self, row: asyncpg.Record) -> AgentItemRead:
        d = dict(row)
        for col in ("content", "metadata"):
            if isinstance(d.get(col), str):
                d[col] = json.loads(d[col])
        return AgentItemRead.model_validate(d)

    async def create(self, doc: AgentItemCreate) -> AgentItemRead:
        sql = """
            INSERT INTO agent_items
                (agent_session_id, prev_item_id, role, sender, content, message_id, metadata)
            VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7::jsonb)
            RETURNING *
        """
        row = await self._pool.fetchrow(
            sql,
            doc.agent_session_id,
            doc.prev_item_id,
            doc.role,
            doc.sender,
            self._to_jsonb(doc.content),
            doc.message_id,
            self._to_jsonb(doc.metadata),
        )
        assert row is not None
        return self._row_to_read(row)

    async def update(self, id: UUID, patch: _ImmutableUpdate) -> NoReturn:  # type: ignore[override]
        raise RuntimeError(
            "agent_items are immutable; update is not supported by design",
        )

    # ---- 특수 쿼리 ----

    async def list_by_session(self, agent_session_id: UUID) -> list[AgentItemRead]:
        """session 안의 모든 item 을 created_at 순으로 반환.

        prev_item_id chain 도 결국 created_at 순과 일치 (단조 증가) 라 단순 정렬로 충분.
        """
        rows = await self._pool.fetch(
            "SELECT * FROM agent_items WHERE agent_session_id = $1 ORDER BY created_at",
            agent_session_id,
        )
        return [self._row_to_read(r) for r in rows]


__all__ = ["AgentItemRepository"]
