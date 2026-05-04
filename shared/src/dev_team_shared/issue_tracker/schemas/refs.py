"""도구가 own 하는 메타데이터 레퍼런스 (status / type).

mcp/CLAUDE.md §0 (thin bridge) 에 따라 도구의 사실을 그대로 노출. enum /
정규화 X. 호출자 (LLM 에이전트) 가 list 결과를 보고 컨텍스트로 판단.

본 파일은 server (mcp/issue-tracker) / client (다른 모듈에서 import) 양쪽이
공유하는 단일 정의. 코드 중복 X.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class StatusRef(BaseModel):
    """Project board 의 status field option 1개.

    `id` 는 후속 호출 식별자 (`transition(ref, status_id=...)`).
    `name` 은 사용자 / 에이전트 표시용.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str


class TypeRef(BaseModel):
    """이슈 트래커의 issue type 1개 (GitHub Project board 의 Type field 등)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str


__all__ = ["StatusRef", "TypeRef"]
