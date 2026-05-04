"""env 기반 설정. lifespan 에서 1회 로드 후 주입."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Document DB MCP 서버 설정.

    env 우선순위 (Pydantic Settings 표준): env var > .env > 기본값.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Postgres dev_team DB 의 DSN. compose 가 주입.
    database_uri: str = Field(
        default="postgres://devteam:devteam_postgres@localhost:5432/dev_team",
        description="dev_team DB 연결 DSN (langgraph DB 와 분리, 이슈 #20)",
    )

    # asyncpg pool 설정
    pool_min_size: int = 2
    pool_max_size: int = 10

    # streamable HTTP 서버 포트 (컨테이너 내부)
    http_port: int = 8000

    # Migration 자동 적용 여부 (테스트 시 끌 수 있게)
    auto_migrate: bool = True


__all__ = ["Settings"]
