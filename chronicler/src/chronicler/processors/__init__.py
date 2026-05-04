"""이벤트 type 별 처리 전략 (Strategy 패턴).

새 이벤트 type 추가 시:
  1. processors/<name>.py — `EventProcessor` 상속한 concrete 작성
  2. 본 파일의 `ALL_PROCESSORS` 에 인스턴스 1줄 추가

handler.py / consumer.py 무수정 (OCP).
"""

from chronicler.processors.base import EventProcessor
from chronicler.processors.item_append import ItemAppendProcessor
from chronicler.processors.session_end import SessionEndProcessor
from chronicler.processors.session_start import SessionStartProcessor

ALL_PROCESSORS: list[EventProcessor] = [
    SessionStartProcessor(),
    ItemAppendProcessor(),
    SessionEndProcessor(),
]
"""기본 등록 목록. main.py 가 이걸 EventHandler 에 주입."""


__all__ = [
    "ALL_PROCESSORS",
    "EventProcessor",
    "ItemAppendProcessor",
    "SessionEndProcessor",
    "SessionStartProcessor",
]
