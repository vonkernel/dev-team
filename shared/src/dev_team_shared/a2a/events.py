"""A2A Protocol v1.0 Task 및 SSE 이벤트 모델.

A2A spec §3 (Task lifecycle) 의 Task 객체, streaming 전송용 업데이트 이벤트
(TaskStatusUpdateEvent / TaskArtifactUpdateEvent), Artifact, TaskStatus 를
Pydantic 모델로 정의.

모든 모델은 `populate_by_name=True` 설정과 Field alias 로 직렬화 시 camelCase,
역직렬화 시 양쪽(모두) 수용한다. `model_dump(by_alias=True, exclude_none=True)`
로 spec 호환 JSON 생성.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from dev_team_shared.a2a.types import Message, Part, TaskState


class TaskStatus(BaseModel):
    """Task 의 현재 상태 (spec §3.2).

    `message` 는 상태 전이에 동반되는 설명성 메시지 (특히 FAILED 시 에러 내용).
    """

    model_config = ConfigDict(populate_by_name=True)

    state: TaskState
    message: Message | None = None
    timestamp: str | None = None


class Artifact(BaseModel):
    """Task 산출물 (spec §3.3).

    streaming 중에는 동일 `artifact_id` 에 대해 chunk 단위로 `append=true`
    이벤트가 누적되어 완성된다.
    """

    model_config = ConfigDict(populate_by_name=True)

    artifact_id: str = Field(alias="artifactId")
    name: str | None = None
    description: str | None = None
    parts: list[Part]


class Task(BaseModel):
    """A2A Task (spec §3.1).

    `SendMessage` 응답의 `result`, `SendStreamingMessage` 의 초기 SSE 이벤트,
    `GetTask` 응답 등에서 공통 사용.
    """

    model_config = ConfigDict(populate_by_name=True)

    kind: Literal["task"] = "task"
    id: str
    context_id: str = Field(alias="contextId")
    status: TaskStatus
    history: list[Message] = Field(default_factory=list)
    artifacts: list[Artifact] | None = None
    metadata: dict[str, Any] | None = None


class TaskStatusUpdateEvent(BaseModel):
    """Task 상태 전이 이벤트 (spec §3.4 SSE).

    `final=True` 이면 해당 Task 의 SSE 스트림이 종료됨을 알림.
    """

    model_config = ConfigDict(populate_by_name=True)

    kind: Literal["status-update"] = "status-update"
    task_id: str = Field(alias="taskId")
    context_id: str = Field(alias="contextId")
    status: TaskStatus
    final: bool = False


class TaskArtifactUpdateEvent(BaseModel):
    """Artifact chunk 이벤트 (spec §3.4 SSE).

    `append=True` 이면 기존 artifact 에 chunk 를 누적, `False` 면 교체.
    `last_chunk=True` 이면 해당 artifact 의 마지막 chunk.
    """

    model_config = ConfigDict(populate_by_name=True)

    kind: Literal["artifact-update"] = "artifact-update"
    task_id: str = Field(alias="taskId")
    context_id: str = Field(alias="contextId")
    artifact: Artifact
    append: bool = False
    last_chunk: bool = Field(default=False, alias="lastChunk")


__all__ = [
    "Artifact",
    "Task",
    "TaskArtifactUpdateEvent",
    "TaskStatus",
    "TaskStatusUpdateEvent",
]
