"""a2a_contexts Pydantic 모델 — A2A 두 에이전트 사이 대화 namespace.

A2A wire `contextId` 와 1:1. session 발 / assignment 발 / standalone (system
trigger) 셋 다 표현 가능 — `parent_session_id` / `parent_assignment_id` 모두
NULL 이면 standalone.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class A2AContextCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context_id: str                                  # A2A wire contextId
    initiator_agent: str
    counterpart_agent: str
    parent_session_id: UUID | None = None
    parent_assignment_id: UUID | None = None
    trace_id: str | None = None
    topic: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class A2AContextUpdate(BaseModel):
    """주로 ended_at / topic / metadata 갱신용."""

    model_config = ConfigDict(extra="forbid")

    topic: str | None = None
    trace_id: str | None = None
    metadata: dict[str, Any] | None = None
    ended_at: datetime | None = None


class A2AContextRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    context_id: str
    initiator_agent: str
    counterpart_agent: str
    parent_session_id: UUID | None
    parent_assignment_id: UUID | None
    trace_id: str | None
    topic: str | None
    metadata: dict[str, Any]
    started_at: datetime
    ended_at: datetime | None
