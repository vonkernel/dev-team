"""sessions Pydantic 모델 — UG↔P/A 한 대화창 (chat tier)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_endpoint: str                              # 'primary' | 'architect'
    initiator: str = "user"
    counterpart: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionUpdate(BaseModel):
    """주로 ended_at / metadata 갱신용."""

    model_config = ConfigDict(extra="forbid")

    metadata: dict[str, Any] | None = None
    ended_at: datetime | None = None


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_endpoint: str
    initiator: str
    counterpart: str
    metadata: dict[str, Any]
    started_at: datetime
    ended_at: datetime | None
