"""Shared utility helpers — 도메인에 묶이지 않는 작은 함수들.

지금: `mask_dsn` (DSN password 마스킹 — 로깅 안전성).
향후 다른 utility 가 늘어나면 책임별로 서브패키지 (`utils/`) 로 승격.
"""

from __future__ import annotations


def mask_dsn(dsn: str) -> str:
    """비밀번호를 마스킹한 DSN (로그 안전성).

    `postgres://user:secret@host/db` → `postgres://user:***@host/db`.
    `@` 또는 `://` 없으면 원본 그대로 반환.
    """
    if "@" in dsn and "://" in dsn:
        scheme, rest = dsn.split("://", 1)
        creds, host = rest.split("@", 1)
        if ":" in creds:
            user = creds.split(":", 1)[0]
            return f"{scheme}://{user}:***@{host}"
    return dsn


__all__ = ["mask_dsn"]
