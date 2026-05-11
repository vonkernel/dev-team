"""a2a_task_artifacts Pydantic 모델 — A2A Task 의 산출물 (Artifact).

Task 가 생성하는 출력물 (예: 설계 문서 / 코드 diff / 테스트 결과). immutable —
update 미노출.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class A2ATaskArtifactCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID                                         # publisher-supplied (#75 PR 4)
    a2a_task_id: UUID
    name: str | None = None
    parts: list[dict[str, Any]] | dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)


class A2ATaskArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    a2a_task_id: UUID
    name: str | None
    parts: list[dict[str, Any]] | dict[str, Any]
    metadata: dict[str, Any]
    created_at: datetime
