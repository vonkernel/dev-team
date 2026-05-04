"""agent_tasks Pydantic 모델."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

AgentTaskStatus = Literal["open", "in_progress", "done", "cancelled"]


class AgentTaskCreate(BaseModel):
    """create 입력 (id 미지정 — DB가 발급)."""

    model_config = ConfigDict(extra="forbid")

    title: str
    description: str | None = None
    status: AgentTaskStatus = "open"
    owner_agent: str | None = None
    issue_refs: list[UUID] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentTaskUpdate(BaseModel):
    """update 입력 — 모든 필드 선택. 명시된 필드만 patch."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    description: str | None = None
    status: AgentTaskStatus | None = None
    owner_agent: str | None = None
    issue_refs: list[UUID] | None = None
    metadata: dict[str, Any] | None = None


class AgentTaskRead(BaseModel):
    """DB row → 외부 노출 형태."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None
    status: AgentTaskStatus
    owner_agent: str | None
    issue_refs: list[UUID]
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime
