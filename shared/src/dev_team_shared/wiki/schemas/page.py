"""WikiPage Pydantic 모델.

server (mcp/wiki) / client (P 등) 공유 단일 정의.

도메인 필드 (`page_type` / `structured`) 는 doc-store 의 `wiki_pages` collection
schema 와 키 일치 (호출자가 doc-store → wiki MCP 양쪽에 같은 모델 사용).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PageCreate(BaseModel):
    """페이지 생성 입력."""

    model_config = ConfigDict(extra="forbid")

    slug: str = Field(
        ...,
        min_length=1,
        max_length=120,
        description="kebab-case. wiki 의 파일명 = `<slug>.md`, URL slug",
    )
    title: str = Field(..., min_length=1, max_length=512)
    content_md: str = Field(default="", description="Markdown 본문 (front matter 제외)")
    page_type: str | None = Field(
        default=None,
        description="도메인 분류 (예: prd / adr / business_rule). free-form str.",
    )
    structured: dict[str, Any] | None = Field(
        default=None,
        description="page_type 별 정의된 구조화 데이터 (free-form dict)",
    )


class PageUpdate(BaseModel):
    """페이지 갱신 patch (slug 불변, exclude_unset 으로 부분 갱신)."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=512)
    content_md: str | None = None
    page_type: str | None = None
    structured: dict[str, Any] | None = None


class PageRead(BaseModel):
    """페이지 단건 조회 결과 — front matter parse 결과 + 본문."""

    model_config = ConfigDict(extra="forbid")

    slug: str
    title: str
    content_md: str = ""
    page_type: str | None = None
    structured: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PageRef(BaseModel):
    """list 결과의 가벼운 ref — 본문 미포함."""

    model_config = ConfigDict(extra="forbid")

    slug: str
    title: str


__all__ = ["PageCreate", "PageRead", "PageRef", "PageUpdate"]
