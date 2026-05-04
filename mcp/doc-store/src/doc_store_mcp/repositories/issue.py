"""IssueRepository — version 컬럼 (optimistic concurrency) 적용."""

from __future__ import annotations

import json
from uuid import UUID

import asyncpg

from doc_store_mcp.repositories.base import PostgresRepositoryBase
from dev_team_shared.doc_store.schemas.issue import IssueCreate, IssueRead, IssueUpdate


class IssueOptimisticLockError(RuntimeError):
    """version mismatch — concurrent update 감지 시."""


class IssueRepository(PostgresRepositoryBase[IssueCreate, IssueUpdate, IssueRead]):
    @property
    def collection_name(self) -> str:
        return "issues"

    def _to_read(self, row: asyncpg.Record) -> IssueRead:
        d = dict(row)
        for col in ("external_refs", "metadata"):
            if isinstance(d.get(col), str):
                d[col] = json.loads(d[col])
        return IssueRead.model_validate(d)

    async def create(self, doc: IssueCreate) -> IssueRead:
        sql = """
            INSERT INTO issues
                (agent_task_id, type, title, body_md, status, parent_issue_id,
                 labels, external_refs, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9::jsonb)
            RETURNING *
        """
        row = await self._pool.fetchrow(
            sql,
            doc.agent_task_id,
            doc.type,
            doc.title,
            doc.body_md,
            doc.status,
            doc.parent_issue_id,
            doc.labels,
            self._to_jsonb(doc.external_refs),
            self._to_jsonb(doc.metadata),
        )
        assert row is not None
        return self._to_read(row)

    async def update(self, id: UUID, patch: IssueUpdate) -> IssueRead | None:
        return await self.update_with_version(id, patch, expected_version=None)

    async def update_with_version(
        self,
        id: UUID,
        patch: IssueUpdate,
        *,
        expected_version: int | None,
    ) -> IssueRead | None:
        """expected_version 지정 시 optimistic lock — mismatch 면 IssueOptimisticLockError."""
        fields = patch.model_dump(exclude_unset=True)
        if not fields:
            return await self.get(id)
        set_clauses: list[str] = []
        params: list[object] = []
        for i, (col, val) in enumerate(fields.items(), start=1):
            if col in ("external_refs", "metadata"):
                set_clauses.append(f"{col} = ${i}::jsonb")
                params.append(self._to_jsonb(val))
            else:
                set_clauses.append(f"{col} = ${i}")
                params.append(val)
        # version + updated_at 자동 갱신
        set_clauses.append("version = version + 1")
        set_clauses.append("updated_at = NOW()")

        if expected_version is not None:
            sql = (
                f"UPDATE issues SET {', '.join(set_clauses)} "
                f"WHERE id = ${len(params) + 1} AND version = ${len(params) + 2} "
                f"RETURNING *"
            )
            params.extend([id, expected_version])
            row = await self._pool.fetchrow(sql, *params)
            if row is None:
                # id 자체가 없는지 / version 불일치인지 구분
                exists = await self._pool.fetchval(
                    "SELECT 1 FROM issues WHERE id = $1", id,
                )
                if exists:
                    raise IssueOptimisticLockError(
                        f"version mismatch on issue {id} "
                        f"(expected={expected_version})",
                    )
                return None
            return self._to_read(row)

        sql = (
            f"UPDATE issues SET {', '.join(set_clauses)} "
            f"WHERE id = ${len(params) + 1} RETURNING *"
        )
        params.append(id)
        row = await self._pool.fetchrow(sql, *params)
        return self._to_read(row) if row else None


__all__ = ["IssueRepository", "IssueOptimisticLockError"]
