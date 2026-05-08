"""a2a_task_status_updates Pydantic 모델 — A2A Task 의 state transition 로그.

Task 의 lifecycle 동안 매 state 전환 (SUBMITTED → WORKING → ... → COMPLETED 등)
별로 1 row 누적. immutable — update 미노출.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from dev_team_shared.doc_store.schemas.a2a_task import A2ATaskState


class A2ATaskStatusUpdateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    a2a_task_id: UUID
    state: A2ATaskState
    reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class A2ATaskStatusUpdateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    a2a_task_id: UUID
    state: A2ATaskState
    transitioned_at: datetime
    reason: str | None
    metadata: dict[str, Any]
