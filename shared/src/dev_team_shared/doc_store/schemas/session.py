"""sessions Pydantic 모델 — UG↔P/A 한 대화창 (chat tier).

#75 PR 3: session 은 종료 개념 없음 (사용자가 언제든 재개) — `ended_at`
필드 / `SessionEndEvent` / `SessionEndProcessor` 모두 폐기. archive 가
필요해지면 별도 컬럼 (예: `archived_at`) 으로.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID | None = None                           # publisher (UG / chronicler) 가 미리 알면 사용
    agent_endpoint: str                              # 'primary' | 'architect'
    initiator: str = "user"
    counterpart: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionUpdate(BaseModel):
    """metadata 갱신용 (ended_at 폐기됨)."""

    model_config = ConfigDict(extra="forbid")

    metadata: dict[str, Any] | None = None


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_endpoint: str
    initiator: str
    counterpart: str
    metadata: dict[str, Any]
    started_at: datetime
