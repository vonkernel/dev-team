"""Page metadata encode / decode — GitHub Wiki UI 친화적 양식.

Wiki 페이지 markdown 의 시작에 다음 형태로 metadata 인코딩:

    ### 📋 Page metadata

    ```yaml
    title: GuestBook PRD
    page_type: prd
    created_at: 2026-05-04T17:39:00Z
    updated_at: 2026-05-04T17:39:00Z
    structured:
      milestones: [{name: M1}]
    ```


    ***

    # 본문...

GitHub Wiki UI 에서 H3 헤더 + yaml syntax-highlighted block + hr 구분자로 깔끔히
표시. yaml block 안의 yaml 만 parse → metadata dict 복원 (round-trip).

이전엔 jekyll-style `---` front matter 사용했으나 GitHub Wiki 는 jekyll 미사용 →
`---` 가 hr + plain text 로 노출되어 지저분했음. 본 양식이 우리 컨벤션.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

import yaml

_HEADER = "### 📋 Page metadata"
_FENCE_OPEN = "```yaml"
_FENCE_CLOSE = "```"
_DIVIDER = "***"

# 양식 매칭: 헤더 → (공백) → ```yaml → yaml block → ``` → (공백) → ***
# 캡처 그룹: yaml block 내용
_BLOCK_RE = re.compile(
    r"\A\s*"
    + re.escape(_HEADER)
    + r"\s*\n\s*"
    + re.escape(_FENCE_OPEN)
    + r"\n(?P<yaml>.*?)\n"
    + re.escape(_FENCE_CLOSE)
    + r"\s*\n\s*"
    + re.escape(_DIVIDER)
    + r"\s*\n",
    re.DOTALL,
)


def encode(metadata: dict[str, Any], content_md: str) -> str:
    """metadata + content → 페이지 텍스트.

    metadata 의 None 값은 dump 에서 제외 (front matter noise 회피).
    """
    cleaned = {k: _serialize(v) for k, v in metadata.items() if v is not None}
    yaml_block = yaml.safe_dump(cleaned, sort_keys=False, allow_unicode=True).rstrip()
    return (
        f"{_HEADER}\n\n"
        f"{_FENCE_OPEN}\n{yaml_block}\n{_FENCE_CLOSE}\n\n\n"
        f"{_DIVIDER}\n\n"
        f"{content_md}"
    )


def decode(text: str) -> tuple[dict[str, Any], str]:
    """페이지 텍스트 → (metadata dict, content_md). 양식 불일치 시 빈 metadata + 원문."""
    match = _BLOCK_RE.match(text)
    if match is None:
        return {}, text
    yaml_block = match.group("yaml")
    rest = text[match.end():].lstrip("\n")
    try:
        metadata = yaml.safe_load(yaml_block) or {}
    except yaml.YAMLError:
        return {}, text
    if not isinstance(metadata, dict):
        return {}, text
    return metadata, rest


def _serialize(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return value


__all__ = ["decode", "encode"]
