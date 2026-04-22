"""A2A Protocol v1.0 데이터 타입.

spec: https://a2a-protocol.org/latest/specification/
proto: https://github.com/a2aproject/A2A/blob/main/specification/a2a.proto

JSON 직렬화 규약 (§5.5):
- 필드명: camelCase
- enum: proto 이름 그대로 SCREAMING_SNAKE_CASE 문자열
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TaskState(StrEnum):
    """A2A TaskState enum. JSON 값은 `TASK_STATE_*` 문자열 그대로."""

    UNSPECIFIED = "TASK_STATE_UNSPECIFIED"
    SUBMITTED = "TASK_STATE_SUBMITTED"
    WORKING = "TASK_STATE_WORKING"
    COMPLETED = "TASK_STATE_COMPLETED"
    FAILED = "TASK_STATE_FAILED"
    CANCELED = "TASK_STATE_CANCELED"
    INPUT_REQUIRED = "TASK_STATE_INPUT_REQUIRED"
    AUTH_REQUIRED = "TASK_STATE_AUTH_REQUIRED"
    REJECTED = "TASK_STATE_REJECTED"


class Role(StrEnum):
    """A2A Message Role enum."""

    UNSPECIFIED = "ROLE_UNSPECIFIED"
    USER = "ROLE_USER"
    AGENT = "ROLE_AGENT"


class Part(BaseModel):
    """A2A Message Part (oneof text/raw/url/data + 공통 메타).

    각 Part 인스턴스는 text/raw/url/data 중 **하나**만 설정되어야 한다 (spec §4.1.5).
    """

    model_config = ConfigDict(populate_by_name=True)

    text: str | None = None
    # raw bytes 는 JSON 으로는 base64. 본 타입은 이미 디코딩된 bytes 또는 base64 문자열을 허용.
    raw: bytes | str | None = None
    url: str | None = None
    data: Any | None = None

    metadata: dict[str, Any] | None = None
    filename: str | None = None
    media_type: str | None = Field(default=None, alias="mediaType")


class Message(BaseModel):
    """A2A Message (spec §4.1.4)."""

    model_config = ConfigDict(populate_by_name=True)

    message_id: str = Field(alias="messageId")
    role: Role
    parts: list[Part]

    context_id: str | None = Field(default=None, alias="contextId")
    task_id: str | None = Field(default=None, alias="taskId")
    metadata: dict[str, Any] | None = None
    extensions: list[str] | None = None
    reference_task_ids: list[str] | None = Field(default=None, alias="referenceTaskIds")


__all__ = ["Message", "Part", "Role", "TaskState"]
