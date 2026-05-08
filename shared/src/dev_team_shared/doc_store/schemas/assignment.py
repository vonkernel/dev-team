"""assignments Pydantic 모델 — 도메인 work item.

P / A 가 chat 중 합의해 발급. 한 Assignment 는 1 개 이상의 A2A Task 로 구성
가능 (`a2a_tasks.assignment_id` 로 backlink).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

AssignmentStatus = Literal["open", "in_progress", "done", "cancelled"]


class AssignmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str | None = None
    status: AssignmentStatus = "open"
    owner_agent: str | None = None
    root_session_id: UUID | None = None              # 어느 chat session 에서 비롯
    issue_refs: list[UUID] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AssignmentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    description: str | None = None
    status: AssignmentStatus | None = None
    owner_agent: str | None = None
    root_session_id: UUID | None = None
    issue_refs: list[UUID] | None = None
    metadata: dict[str, Any] | None = None


class AssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None
    status: AssignmentStatus
    owner_agent: str | None
    root_session_id: UUID | None
    issue_refs: list[UUID]
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime
