"""env 기반 설정. lifespan 에서 1회 로드 후 어댑터에 주입."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Wiki MCP 서버 설정."""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_ignore_empty=True,
    )

    wiki_type: str = Field(default="github", description="구현체 식별자 (github / ...)")

    # GitHub 어댑터 전용
    github_token: str = Field(default="", description="PAT, scope: repo (wiki 권한 포함)")
    github_target_owner: str = Field(default="", description="대상 저장소 owner")
    github_target_repo: str = Field(default="", description="대상 저장소 name")

    # streamable HTTP 서버 포트 (컨테이너 내부)
    http_port: int = 8000


__all__ = ["Settings"]
