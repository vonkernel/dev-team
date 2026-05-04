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


class FieldRef(BaseModel):
    """Project board 의 field 1개 (Status / Type / Priority 등 어떤 field 든).

    P 가 board 에 어떤 field 가 있는지 조회하고 (`field.list`), 부족하면
    `field.create` 로 직접 추가하기 위함. board setup 자체를 PM 워크플로우로
    내재화 — 사람이 board UI 에서 사전 setup 하지 않아도 됨.

    `kind` 는 GitHub 의 dataType 을 lowercase + underscore 로 정규화한 값
    (예: "single_select", "text", "number", "date", "iteration"). 우리 시스템
    의 status / type 도구는 `single_select` 만 의미 있음.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    kind: str


__all__ = ["FieldRef", "StatusRef", "TypeRef"]
