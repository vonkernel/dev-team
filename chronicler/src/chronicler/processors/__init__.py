"""이벤트 type 별 처리 전략 (Strategy 패턴).

#75 PR 2: chat / assignment / a2a 3 layer 의 11 processor.

새 이벤트 type 추가 시:
  1. processors/<name>.py — `EventProcessor` 상속한 concrete 작성
  2. 본 파일의 `ALL_PROCESSORS` 에 인스턴스 1줄 추가

handler.py / consumer.py 무수정 (OCP).
"""

from chronicler.processors.a2a_context_end import A2AContextEndProcessor
from chronicler.processors.a2a_context_start import A2AContextStartProcessor
from chronicler.processors.a2a_message_append import A2AMessageAppendProcessor
from chronicler.processors.a2a_task_artifact import A2ATaskArtifactProcessor
from chronicler.processors.a2a_task_create import A2ATaskCreateProcessor
from chronicler.processors.a2a_task_status_update import (
    A2ATaskStatusUpdateProcessor,
)
from chronicler.processors.assignment_create import AssignmentCreateProcessor
from chronicler.processors.assignment_update import AssignmentUpdateProcessor
from chronicler.processors.base import EventProcessor
from chronicler.processors.chat_append import ChatAppendProcessor
from chronicler.processors.chat_session_end import ChatSessionEndProcessor
from chronicler.processors.chat_session_start import ChatSessionStartProcessor

ALL_PROCESSORS: list[EventProcessor] = [
    # Chat layer
    ChatSessionStartProcessor(),
    ChatAppendProcessor(),
    ChatSessionEndProcessor(),
    # Assignment layer
    AssignmentCreateProcessor(),
    AssignmentUpdateProcessor(),
    # A2A layer
    A2AContextStartProcessor(),
    A2AMessageAppendProcessor(),
    A2ATaskCreateProcessor(),
    A2ATaskStatusUpdateProcessor(),
    A2ATaskArtifactProcessor(),
    A2AContextEndProcessor(),
]
"""기본 등록 목록. main.py 가 EventHandler 에 주입."""


__all__ = [
    "A2AContextEndProcessor",
    "A2AContextStartProcessor",
    "A2AMessageAppendProcessor",
    "A2ATaskArtifactProcessor",
    "A2ATaskCreateProcessor",
    "A2ATaskStatusUpdateProcessor",
    "ALL_PROCESSORS",
    "AssignmentCreateProcessor",
    "AssignmentUpdateProcessor",
    "ChatAppendProcessor",
    "ChatSessionEndProcessor",
    "ChatSessionStartProcessor",
    "EventProcessor",
]
