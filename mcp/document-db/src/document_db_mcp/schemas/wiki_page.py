"""wiki_pages Pydantic 모델."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

WikiPageType = Literal[
    "prd", "business_rule", "data_model",
    "adr", "api_contract",
    "glossary", "runbook", "generic",
]
WikiPageStatus = Literal["draft", "confirmed", "cancelled"]


class WikiPageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_task_id: UUID | None = None
    page_type: WikiPageType
    slug: str
    title: str
    content_md: str
    status: WikiPageStatus = "draft"
    author_agent: str | None = None
    references_issues: list[UUID] = Field(default_factory=list)
    references_pages: list[UUID] = Field(default_factory=list)
    structured: dict[str, Any] = Field(default_factory=dict)
    external_refs: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WikiPageUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    content_md: str | None = None
    status: WikiPageStatus | None = None
    references_issues: list[UUID] | None = None
    references_pages: list[UUID] | None = None
    structured: dict[str, Any] | None = None
    external_refs: dict[str, Any] | None = None
    last_synced_at: datetime | None = None
    metadata: dict[str, Any] | None = None


class WikiPageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_task_id: UUID | None
    page_type: WikiPageType
    slug: str
    title: str
    content_md: str
    status: WikiPageStatus
    author_agent: str | None
    references_issues: list[UUID]
    references_pages: list[UUID]
    structured: dict[str, Any]
    external_refs: dict[str, Any]
    last_synced_at: datetime | None
    metadata: dict[str, Any]
    version: int
    created_at: datetime
    updated_at: datetime
