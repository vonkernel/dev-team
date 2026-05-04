"""DB 연결 + 마이그레이션 적용.

asyncpg pool 생성 / cleanup, yoyo 기반 마이그레이션 자동 적용.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import asyncpg
from yoyo import get_backend, read_migrations

logger = logging.getLogger(__name__)

# 본 모듈 위치 기준 migrations 디렉터리 경로
_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


def apply_migrations(database_uri: str) -> None:
    """yoyo-migrations 로 마이그레이션 자동 적용.

    yoyo 는 sync API 라 asyncio 컨텍스트 밖에서 호출 (lifespan 에서 to_thread).
    `_yoyo_migration` 테이블로 적용 상태 추적, idempotent.
    """
    # yoyo 는 postgresql+psycopg:// 스키마로 psycopg3 driver 사용 (langgraph 와 동일)
    yoyo_uri = database_uri.replace("postgres://", "postgresql+psycopg://", 1)
    if not yoyo_uri.startswith("postgresql+psycopg://"):
        # 이미 postgresql:// 면 그대로 두지 않고 psycopg3 로
        yoyo_uri = yoyo_uri.replace("postgresql://", "postgresql+psycopg://", 1)
    backend = get_backend(yoyo_uri)
    migrations = read_migrations(str(_MIGRATIONS_DIR))
    with backend.lock():
        backend.apply_migrations(backend.to_apply(migrations))
    logger.info("migrations applied (dir=%s)", _MIGRATIONS_DIR)


@asynccontextmanager
async def pool_lifespan(
    database_uri: str,
    *,
    min_size: int = 2,
    max_size: int = 10,
) -> AsyncIterator[asyncpg.Pool]:
    """asyncpg Pool 생성 / 정리 컨텍스트.

    server.py lifespan 에서 사용 — DI 진입점.
    """
    pool = await asyncpg.create_pool(
        dsn=database_uri,
        min_size=min_size,
        max_size=max_size,
    )
    try:
        logger.info("asyncpg pool ready (min=%d, max=%d)", min_size, max_size)
        yield pool
    finally:
        await pool.close()
        logger.info("asyncpg pool closed")


__all__ = ["apply_migrations", "pool_lifespan"]
