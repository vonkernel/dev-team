"""EventProcessor — 이벤트 type 1개 처리 계약 (Strategy + Registry).

새 type 추가 시 본 ABC 를 상속한 concrete 를 작성하고 `processors/__init__.py`
의 `ALL_PROCESSORS` 에 등록만 하면 됨. handler.py / consumer.py 본문 수정 불필요.

Processor 는 typed `DocumentDbClient` 만 의존. wire-level (도구명 / dict / JSON
parse) 은 client 안에 격리되어 본 ABC 외부로 새지 않음.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from dev_team_shared.document_db import DocumentDbClient
from dev_team_shared.event_bus.events import A2AEvent


class EventProcessor(ABC):
    """A2A 이벤트 1 type 의 처리 책임.

    `event_type` ClassVar 가 dispatch key. 등록 시 `EventHandler` 가
    `{event_type: processor}` 매핑으로 보관.
    """

    event_type: ClassVar[type[A2AEvent]]

    @abstractmethod
    async def process(self, event: A2AEvent, db: DocumentDbClient) -> None:
        """이벤트 1건을 typed Document DB client 호출로 영속화.

        실패 시 raise — consumer 가 PEL 에 남겨 재시도 처리.
        """


__all__ = ["EventProcessor"]
