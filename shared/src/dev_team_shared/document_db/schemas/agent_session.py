"""agent_sessions Pydantic 모델."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AgentSessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_task_id: UUID
    initiator: str
    counterpart: str
    context_id: str
    trace_id: str | None = None
    topic: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentSessionUpdate(BaseModel):
    """주로 ended_at / topic / metadata 갱신용."""

    model_config = ConfigDict(extra="forbid")

    topic: str | None = None
    trace_id: str | None = None
    metadata: dict[str, Any] | None = None
    ended_at: datetime | None = None


class AgentSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_task_id: UUID
    initiator: str
    counterpart: str
    context_id: str
    trace_id: str | None
    topic: str | None
    metadata: dict[str, Any]
    started_at: datetime
    ended_at: datetime | None
