"""Repository 추상 (`AbstractRepository`) + Postgres backend base (`PostgresRepositoryBase`).

OCP / DIP 정공법으로 두 계층 분리:

- **`AbstractRepository`** — backend 무관한 순수 계약. collection 이름 + 6 추상
  method. 본 ABC 만 보면 어떤 backend (Postgres / Mongo / 메모리 등) 도 구현
  가능. tools 레이어가 본 ABC 만 의존하면 backend 교체 자유.

- **`PostgresRepositoryBase`** — Postgres backend 의 generic 5 op SQL 구현
  (`get` / `list` / `delete` / `count` / `_where_clause`). concrete 가 본
  클래스를 상속하면 SQL 공통 부분 자동 사용. concrete 는 `collection_name`,
  `_to_read`, `create`, `update` 만 작성.

향후 다른 backend 추가 시: `MongoRepositoryBase(AbstractRepository)` 같은 형제
신설 — 모듈 내부 OCP 확장 (모듈 / 패키지 폭발 X).
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

    where: dict[str, Any] | None = None
    limit: int = 100
    offset: int = 0
    order_by: str = "created_at DESC"


# ─────────────────────────────────────────────────────────────────────────────
#  AbstractRepository — backend 무관 진짜 추상
# ─────────────────────────────────────────────────────────────────────────────


class AbstractRepository(ABC, Generic[CreateT, UpdateT, ReadT]):
    """Collection 별 CRUD 추상. backend (Postgres / Mongo / ...) 무관 계약.

    호출자 (tools / repository factory) 는 본 ABC 만 의존. concrete 는 backend
    별 base (예: `PostgresRepositoryBase`) 를 거쳐 구현.
    """

    @property
    @abstractmethod
    def collection_name(self) -> str:
        """대상 collection 이름. e.g. 'agent_tasks'."""

    @abstractmethod
    async def create(self, doc: CreateT) -> ReadT:
        """신규 record insert."""

    @abstractmethod
    async def update(self, id: UUID, patch: UpdateT) -> ReadT | None:
        """patch update. None 반환 = id 미존재."""

    @abstractmethod
    async def get(self, id: UUID) -> ReadT | None:
        """단건 조회."""

    @abstractmethod
    async def list(self, flt: ListFilter | None = None) -> list[ReadT]:
        """필터 / 페이지네이션 조회."""

    @abstractmethod
    async def delete(self, id: UUID) -> bool:
        """삭제. True = 삭제됨, False = id 미존재."""

    @abstractmethod
    async def count(self, where: dict[str, Any] | None = None) -> int:
        """필터 일치 수."""


# ─────────────────────────────────────────────────────────────────────────────
#  PostgresRepositoryBase — Postgres backend 의 SQL 공통 구현
# ─────────────────────────────────────────────────────────────────────────────


class PostgresRepositoryBase(
    AbstractRepository[CreateT, UpdateT, ReadT],
    Generic[CreateT, UpdateT, ReadT],
):
    """Postgres / asyncpg backend 의 5 op SQL 공통 구현.

    Concrete 는 본 클래스를 상속하고 다음만 구현:
      - `collection_name` (table 이름)
      - `_to_read(record)` — asyncpg.Record → ReadT 변환
      - `create` — INSERT SQL
      - `update` — UPDATE SQL (collection 별 컬럼 다름)

    `get` / `list` / `delete` / `count` 는 본 클래스가 SQL 자동 생성 후 실행.
    `version` 컬럼 있는 collection (issues / wiki_pages) 은 update 를 override
    해 optimistic locking 추가.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    @abstractmethod
    def _to_read(self, record: asyncpg.Record) -> ReadT:
        """asyncpg Record → ReadT 변환. JSONB / array 직렬화 처리는 여기서."""

    # ----- 공통 SQL 구현 -----

    async def get(self, id: UUID) -> ReadT | None:
        sql = f"SELECT * FROM {self.collection_name} WHERE id = $1"  # noqa: S608 — collection_name 은 abstract property, 외부 입력 X
        record = await self._pool.fetchrow(sql, id)
        return self._to_read(record) if record else None

    async def delete(self, id: UUID) -> bool:
        sql = f"DELETE FROM {self.collection_name} WHERE id = $1"  # noqa: S608
        result = await self._pool.execute(sql, id)
        # asyncpg execute returns 'DELETE N' string
        return result.endswith(" 1")

    async def list(self, flt: ListFilter | None = None) -> list[ReadT]:
        flt = flt or ListFilter()
        where_sql, params = self._where_clause(flt.where or {})
        # order_by / limit / offset 은 caller-controlled (관리자 사용) 이지만
        # tools 레이어가 화이트리스트 검증해서 SQL 인젝션 방어해야 함.
        sql = (
            f"SELECT * FROM {self.collection_name} {where_sql} "  # noqa: S608
            f"ORDER BY {flt.order_by} "
            f"LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}"
        )
        records = await self._pool.fetch(sql, *params, flt.limit, flt.offset)
        return [self._to_read(r) for r in records]

    async def count(self, where: dict[str, Any] | None = None) -> int:
        where_sql, params = self._where_clause(where or {})
        sql = f"SELECT COUNT(*) FROM {self.collection_name} {where_sql}"  # noqa: S608
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


__all__ = ["AbstractRepository", "ListFilter", "PostgresRepositoryBase"]
