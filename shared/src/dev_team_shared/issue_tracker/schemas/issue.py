"""Issue 도메인 모델 (Pydantic Create / Update / Read).

추상화 방침 (root CLAUDE.md "에이전트 ↔ 외부 도구 운영 원칙" + mcp/CLAUDE.md §0):
- status / type 모두 raw str — 호출자(LLM) 가 list 결과의 id 들고 넘김. enum X.
- IssueRead 의 status / type 은 도구 fact 그대로 (StatusRef / TypeRef).
- Create / Update / Read 분리 (mcp/CLAUDE.md §1.5).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from dev_team_shared.issue_tracker.schemas.refs import StatusRef, TypeRef


class IssueCreate(BaseModel):
    """이슈 생성 입력. 호출자 (P) 가 컨텍스트 기반으로 type / status 결정."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=512)
    body: str | None = Field(default=None, description="Markdown 본문. PRD 링크 등")
    type_id: str | None = Field(
        default=None,
        description="`type.list` 결과의 TypeRef.id. None 이면 type 미지정.",
    )
    status_id: str | None = Field(
        default=None,
        description=(
            "초기 status. `status.list` 결과의 StatusRef.id. "
            "None 이면 board 디폴트 (보통 Backlog) 로 등록."
        ),
    )


class IssueUpdate(BaseModel):
    """이슈 갱신 patch. 모든 필드 Optional, exclude_unset 으로 부분 갱신."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=512)
    body: str | None = None
    type_id: str | None = None


class IssueRead(BaseModel):
    """이슈 단건 조회 결과 — 도구 fact 그대로."""

    model_config = ConfigDict(extra="forbid")

    ref: str = Field(..., description="이슈 식별자 (GitHub: issue number 문자열)")
    title: str
    body: str | None = None
    type: TypeRef | None = None
    status: StatusRef | None = None
    closed: bool = False
    created_at: datetime
    updated_at: datetime


__all__ = ["IssueCreate", "IssueUpdate", "IssueRead"]
