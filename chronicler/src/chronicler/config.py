"""env 로딩."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Chronicler 설정."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 인프라 endpoint
    valkey_url: str = "redis://valkey:6379"
    document_db_mcp_url: str = "http://document-db-mcp:8000/mcp"

    # Consumer Group / Name (proposal §2.6)
    consumer_group: str = Field(default="chronicler", alias="CHRONICLER_CONSUMER_GROUP")
    consumer_name: str = Field(default="chr-1", alias="CHRONICLER_CONSUMER_NAME")

    # 한 번에 fetch 할 메시지 수
    batch_size: int = 10
    # 메시지 없을 때 block 대기 (ms)
    block_ms: int = 5000


__all__ = ["Settings"]
