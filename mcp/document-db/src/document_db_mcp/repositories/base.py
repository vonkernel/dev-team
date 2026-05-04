"""AbstractRepository — collection 별 CRUD 의 공통 계약 (DIP / OCP).

새 collection 추가 시 본 ABC 를 상속해 concrete 작성. tools 는 ABC 만 의존.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Generic, TypeVar
from uuid import UUID

import asyncpg
from pydantic import BaseModel

CreateT = TypeVar("CreateT", bound=BaseModel)
UpdateT = TypeVar("UpdateT", bound=BaseModel)
ReadT = TypeVar("ReadT", bound=BaseModel)


@dataclass(frozen=True)
class ListFilter:
    """list 조회 시 사용. 단순 equality 매칭만 (복잡 쿼리는 collection 별 메서드)."""

    where: dict[str, Any] | None = None  # column → value
    limit: int = 100
    offset: int = 0
    order_by: str = "created_at DESC"


class AbstractRepository(ABC, Generic[CreateT, UpdateT, ReadT]):
    """5 op generic CRUD. concrete 가 table 이름 / row → model 변환만 채우면 됨.

    `version` 컬럼이 있는 collection (issues / wiki_pages) 의 optimistic locking 은
    concrete 에서 update / upsert override 로 처리.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    @property
    @abstractmethod
    def table_name(self) -> str:
        """대상 테이블명. e.g. 'agent_tasks'."""

    @abstractmethod
    def _row_to_read(self, row: asyncpg.Record) -> ReadT:
        """DB row → ReadT 변환. JSONB / array 직렬화 처리는 여기서."""

    @abstractmethod
    async def create(self, doc: CreateT) -> ReadT:
        """insert. concrete 가 컬럼 목록 / VALUES 작성 책임."""

    @abstractmethod
    async def update(self, id: UUID, patch: UpdateT) -> ReadT | None:
        """patch update. None 반환 = id 미존재."""

    # ----- 공통 구현 (concrete 가 override 필요 없음) -----

    async def get(self, id: UUID) -> ReadT | None:
        sql = f"SELECT * FROM {self.table_name} WHERE id = $1"  # noqa: S608 — table_name 은 abstract property, 외부 입력 X
        row = await self._pool.fetchrow(sql, id)
        return self._row_to_read(row) if row else None

    async def delete(self, id: UUID) -> bool:
        sql = f"DELETE FROM {self.table_name} WHERE id = $1"  # noqa: S608
        result = await self._pool.execute(sql, id)
        # asyncpg execute returns 'DELETE N' string
        return result.endswith(" 1")

    async def list(self, flt: ListFilter | None = None) -> list[ReadT]:
        flt = flt or ListFilter()
        where_sql, params = self._where_clause(flt.where or {})
        # order_by / limit / offset 은 caller-controlled (관리자 사용) 이지만
        # tools 레이어가 화이트리스트 검증해서 SQL 인젝션 방어해야 함.
        sql = (
            f"SELECT * FROM {self.table_name} {where_sql} "  # noqa: S608
            f"ORDER BY {flt.order_by} "
            f"LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}"
        )
        rows = await self._pool.fetch(sql, *params, flt.limit, flt.offset)
        return [self._row_to_read(r) for r in rows]

    async def count(self, where: dict[str, Any] | None = None) -> int:
        where_sql, params = self._where_clause(where or {})
        sql = f"SELECT COUNT(*) FROM {self.table_name} {where_sql}"  # noqa: S608
        return await self._pool.fetchval(sql, *params) or 0

    @staticmethod
    def _where_clause(where: dict[str, Any]) -> tuple[str, list[Any]]:
        """단순 equality WHERE — 기본 op 만. 복잡 쿼리는 collection 별 메서드로."""
        if not where:
            return "", []
        clauses: list[str] = []
        params: list[Any] = []
        for i, (col, val) in enumerate(where.items(), start=1):
            clauses.append(f"{col} = ${i}")
            params.append(val)
        return "WHERE " + " AND ".join(clauses), params

    @staticmethod
    def _to_jsonb(value: Any) -> str:
        """asyncpg 가 dict 를 JSONB 로 자동 매핑하지 않아 명시 직렬화."""
        return json.dumps(value)


__all__ = ["AbstractRepository", "ListFilter"]
