"""issues Pydantic 모델."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

IssueType = Literal["epic", "story", "task"]
IssueStatus = Literal["draft", "confirmed", "cancelled"]


class IssueCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_task_id: UUID | None = None
    type: IssueType
    title: str
    body_md: str
    status: IssueStatus = "draft"
    parent_issue_id: UUID | None = None
    labels: list[str] = Field(default_factory=list)
    external_refs: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class IssueUpdate(BaseModel):
    """update — 명시된 필드만 patch. version 은 optimistic concurrency 용 매개로 별도 인자."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    body_md: str | None = None
    status: IssueStatus | None = None
    parent_issue_id: UUID | None = None
    labels: list[str] | None = None
    external_refs: dict[str, Any] | None = None
    last_synced_at: datetime | None = None
    metadata: dict[str, Any] | None = None


class IssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_task_id: UUID | None
    type: IssueType
    title: str
    body_md: str
    status: IssueStatus
    parent_issue_id: UUID | None
    labels: list[str]
    external_refs: dict[str, Any]
    last_synced_at: datetime | None
    metadata: dict[str, Any]
    version: int
    created_at: datetime
    updated_at: datetime
