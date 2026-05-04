"""EventHandler — Strategy + Registry dispatch.

processors/ 의 EventProcessor 들을 type 별 registry 로 보관 → 들어온 이벤트의
type 으로 lookup 후 해당 processor 의 process() 호출.

새 이벤트 type 추가 시 본 파일 수정 불필요 (OCP). 새 processor 작성 +
processors/__init__.py 의 ALL_PROCESSORS 에 인스턴스 추가만.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from dev_team_shared.document_db import DocumentDbClient
from dev_team_shared.event_bus.events import A2AEvent

from chronicler.processors.base import EventProcessor

logger = logging.getLogger(__name__)


class EventHandler:
    """이벤트 → 적절한 processor 로 dispatch.

    중복 등록 (같은 event_type 두 번) 은 ValueError — 등록 시점에 조기 차단.
    """

    def __init__(
        self,
        processors: Iterable[EventProcessor],
        db: DocumentDbClient,
    ) -> None:
        self._db = db
        self._registry: dict[type[A2AEvent], EventProcessor] = {}
        for p in processors:
            if p.event_type in self._registry:
                raise ValueError(
                    f"duplicate processor for event type {p.event_type.__name__}: "
                    f"{type(self._registry[p.event_type]).__name__} vs "
                    f"{type(p).__name__}",
                )
            self._registry[p.event_type] = p

    @property
    def registered_event_types(self) -> tuple[type[A2AEvent], ...]:
        """consumer 가 wire→python type 매핑 도출 시 사용."""
        return tuple(self._registry.keys())

    async def handle(self, event: A2AEvent) -> None:
        processor = self._registry.get(type(event))
        if processor is None:
            logger.warning(
                "no processor registered for event type %s — skip",
                type(event).__name__,
            )
            return
        await processor.process(event, self._db)


__all__ = ["EventHandler"]
