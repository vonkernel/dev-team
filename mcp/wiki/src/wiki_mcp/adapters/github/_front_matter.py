"""YAML front matter encode / decode.

Wiki 페이지 markdown 의 시작에 다음 형태로 metadata 인코딩:

    ---
    title: GuestBook PRD
    page_type: prd
    created_at: 2026-05-04T17:39:00Z
    updated_at: 2026-05-04T17:39:00Z
    structured:
      milestones: [{name: M1}]
    ---

    # 본문...

표준 필드 (`title`, `created_at`, `updated_at`) + 도메인 필드 (`page_type`,
`structured`) 한 곳에 통합.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import yaml

_DELIM = "---"


def encode(metadata: dict[str, Any], content_md: str) -> str:
    """metadata + content → 페이지 텍스트 (front matter 포함)."""
    # datetime → ISO string (yaml.safe_dump 가 datetime 도 처리하지만 명시적으로)
    cleaned = {k: _serialize(v) for k, v in metadata.items() if v is not None}
    fm = yaml.safe_dump(cleaned, sort_keys=False, allow_unicode=True).rstrip()
    return f"{_DELIM}\n{fm}\n{_DELIM}\n\n{content_md}"


def decode(text: str) -> tuple[dict[str, Any], str]:
    """페이지 텍스트 → (metadata dict, content_md). front matter 없으면 빈 dict."""
    stripped = text.lstrip()
    if not stripped.startswith(_DELIM):
        return {}, text

    # `---` 시작 후 다음 `---` 까지 yaml block.
    after_first = stripped[len(_DELIM):].lstrip("\n")
    end = after_first.find(f"\n{_DELIM}")
    if end == -1:
        return {}, text  # 닫는 delim 없음 — front matter 무시

    yaml_block = after_first[:end]
    rest = after_first[end + len(_DELIM) + 1:].lstrip("\n")
    try:
        metadata = yaml.safe_load(yaml_block) or {}
    except yaml.YAMLError:
        return {}, text
    if not isinstance(metadata, dict):
        return {}, text
    return metadata, rest


def _serialize(value: Any) -> Any:
    if isinstance(value, datetime):
        # ISO 8601 + Z (UTC 명시)
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return value


__all__ = ["decode", "encode"]
