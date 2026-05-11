"""a2a_tasks Pydantic 모델 — A2A `Task` 객체 영속.

stateful long-running work tracking. 응답 형식 차원에선 Message 와 alternative
(스펙: "Tasks for Stateful Interactions"). Task 가 commit 된 후엔 관련 Message
들이 `a2a_messages.a2a_task_id` 로 backlink (Task.history).

도메인 Assignment 와는 다른 객체 — `assignment_id` 로 어느 도메인 work item
의 진행을 위해 만들어진 A2A Task 인지 표시.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

A2ATaskState = Literal[
    "SUBMITTED", "WORKING", "COMPLETED", "INPUT_REQUIRED", "FAILED",
]


class A2ATaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID                                         # publisher-supplied (#75 PR 4)
    a2a_context_id: UUID
    state: A2ATaskState = "SUBMITTED"
    assignment_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class A2ATaskUpdate(BaseModel):
    """state 전환 + completed_at 갱신용. state transition 자체의 audit log 는
    `a2a_task_status_updates` 테이블에서 별도 누적."""

    model_config = ConfigDict(extra="forbid")

    state: A2ATaskState | None = None
    completed_at: datetime | None = None
    assignment_id: UUID | None = None
    metadata: dict[str, Any] | None = None


class A2ATaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    a2a_context_id: UUID
    state: A2ATaskState
    submitted_at: datetime
    completed_at: datetime | None
    assignment_id: UUID | None
    metadata: dict[str, Any]
