"""Librarian 의 lifespan 설정 — env 변수 격리.

env 변수 read 를 lifespan 본문에서 분리. 필수 / 선택 구분과 검증을 한 곳에.
Primary 의 settings.py 와 동일 패턴.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class Settings:
    """env 변수에서 읽은 lifespan 설정.

    필수: doc_store_url. 미설정 시 from_env 가 실패.
    선택: database_uri (체크포인터 영속), valkey_url (A2A event publish).
    """

    doc_store_url: str
    database_uri: str | None
    valkey_url: str | None

    @classmethod
    def from_env(cls) -> Settings:
        doc_store_url = os.environ.get("DOC_STORE_MCP_URL")
        if not doc_store_url:
            raise RuntimeError("DOC_STORE_MCP_URL env required")
        return cls(
            doc_store_url=doc_store_url,
            database_uri=os.environ.get("DATABASE_URI"),
            valkey_url=os.environ.get("VALKEY_URL"),
        )


__all__ = ["Settings"]
