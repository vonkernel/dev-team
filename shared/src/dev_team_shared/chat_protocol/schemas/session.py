"""Chat session — 대화창 단위 lifecycle schemas.

`POST /api/sessions` body / response, `GET /api/sessions[/X]` 응답,
`PATCH /api/sessions/{id}` body.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SessionCreateRequest(BaseModel):
    """`POST /api/sessions` body — 사용자가 새 chat 시작.

    `agent_endpoint` 는 사용자가 어느 agent 와 대화할지 선택 (Primary / Architect).
    M3 엔 primary 만 지원, M4+ architect 추가.
    """

    model_config = ConfigDict(extra="forbid")

    agent_endpoint: Literal["primary", "architect"] = "primary"
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionRead(BaseModel):
    """session 조회 결과 — `POST /api/sessions` 응답 + `GET /api/sessions[/X]`."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_endpoint: str
    initiator: str
    counterpart: str
    metadata: dict[str, Any]
    started_at: datetime


class SessionUpdateRequest(BaseModel):
    """`PATCH /api/sessions/{id}` body — metadata 일부 갱신.

    표준 키 (`title` / `pinned` / `last_chat_at` / `unread_count`) 또는 비표준
    키 자유 (JSONB). server 가 받은 dict 를 sessions.metadata 에 merge.
    """

    model_config = ConfigDict(extra="forbid")

    metadata: dict[str, Any]


__all__ = [
    "SessionCreateRequest",
    "SessionRead",
    "SessionUpdateRequest",
]
