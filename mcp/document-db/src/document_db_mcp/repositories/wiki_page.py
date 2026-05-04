"""WikiPageRepository — version + slug UNIQUE."""

from __future__ import annotations

import json
from uuid import UUID

import asyncpg

from document_db_mcp.repositories.base import AbstractRepository
from dev_team_shared.document_db.schemas.wiki_page import (
    WikiPageCreate,
    WikiPageRead,
    WikiPageUpdate,
)


class WikiPageOptimisticLockError(RuntimeError):
    """version mismatch."""


class WikiPageRepository(
    AbstractRepository[WikiPageCreate, WikiPageUpdate, WikiPageRead],
):
    @property
    def table_name(self) -> str:
        return "wiki_pages"

    def _row_to_read(self, row: asyncpg.Record) -> WikiPageRead:
        d = dict(row)
        for col in ("structured", "external_refs", "metadata"):
            if isinstance(d.get(col), str):
                d[col] = json.loads(d[col])
        return WikiPageRead.model_validate(d)

    async def create(self, doc: WikiPageCreate) -> WikiPageRead:
        sql = """
            INSERT INTO wiki_pages
                (agent_task_id, page_type, slug, title, content_md, status,
                 author_agent, references_issues, references_pages,
                 structured, external_refs, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb, $11::jsonb, $12::jsonb)
            RETURNING *
        """
        row = await self._pool.fetchrow(
            sql,
            doc.agent_task_id,
            doc.page_type,
            doc.slug,
            doc.title,
            doc.content_md,
            doc.status,
            doc.author_agent,
            doc.references_issues,
            doc.references_pages,
            self._to_jsonb(doc.structured),
            self._to_jsonb(doc.external_refs),
            self._to_jsonb(doc.metadata),
        )
        assert row is not None
        return self._row_to_read(row)

    async def update(self, id: UUID, patch: WikiPageUpdate) -> WikiPageRead | None:
        return await self.update_with_version(id, patch, expected_version=None)

    async def update_with_version(
        self,
        id: UUID,
        patch: WikiPageUpdate,
        *,
        expected_version: int | None,
    ) -> WikiPageRead | None:
        fields = patch.model_dump(exclude_unset=True)
        if not fields:
            return await self.get(id)
        set_clauses: list[str] = []
        params: list[object] = []
        for i, (col, val) in enumerate(fields.items(), start=1):
            if col in ("structured", "external_refs", "metadata"):
                set_clauses.append(f"{col} = ${i}::jsonb")
                params.append(self._to_jsonb(val))
            else:
                set_clauses.append(f"{col} = ${i}")
                params.append(val)
        set_clauses.append("version = version + 1")
        set_clauses.append("updated_at = NOW()")

        if expected_version is not None:
            sql = (
                f"UPDATE wiki_pages SET {', '.join(set_clauses)} "
                f"WHERE id = ${len(params) + 1} AND version = ${len(params) + 2} "
                f"RETURNING *"
            )
            params.extend([id, expected_version])
            row = await self._pool.fetchrow(sql, *params)
            if row is None:
                exists = await self._pool.fetchval(
                    "SELECT 1 FROM wiki_pages WHERE id = $1", id,
                )
                if exists:
                    raise WikiPageOptimisticLockError(
                        f"version mismatch on wiki_page {id} "
                        f"(expected={expected_version})",
                    )
                return None
            return self._row_to_read(row)

        sql = (
            f"UPDATE wiki_pages SET {', '.join(set_clauses)} "
            f"WHERE id = ${len(params) + 1} RETURNING *"
        )
        params.append(id)
        row = await self._pool.fetchrow(sql, *params)
        return self._row_to_read(row) if row else None

    # ---- 특수 쿼리 ----

    async def get_by_slug(self, slug: str) -> WikiPageRead | None:
        row = await self._pool.fetchrow(
            "SELECT * FROM wiki_pages WHERE slug = $1", slug,
        )
        return self._row_to_read(row) if row else None


__all__ = ["WikiPageRepository", "WikiPageOptimisticLockError"]
