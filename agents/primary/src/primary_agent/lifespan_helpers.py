"""Primary lifespan 의 agent-specific helper.

shared 인 부분 (`build_event_bus`, `build_checkpointer`, `mask_dsn`) 은
`dev_team_shared.lifespan` 으로 추출됨. 본 모듈은 Primary 특수 helper 만:

- `log_runtime_ready` — Primary 의 4 채널 (Doc Store / IssueTracker / Wiki /
  Librarian) 카탈로그 한 줄 요약

shared helper 는 본 모듈에서 re-export — server.py 등의 import 경로 호환.
"""

from __future__ import annotations

import logging

# shared helpers — server.py 가 본 모듈에서 import 하는 호환성 위해 re-export.
from dev_team_shared.lifespan import (  # noqa: F401  re-export
    build_checkpointer,
    build_event_bus,
    mask_dsn,
)
from langchain_core.tools import BaseTool

from primary_agent.channels import Channels

logger = logging.getLogger(__name__)


def log_runtime_ready(channels: Channels, tools: list[BaseTool]) -> None:
    """기동 완료 시점의 채널 / tool 카탈로그 한 줄 요약."""
    logger.info(
        "primary tools wired: doc_store=on, issue_tracker=%s, wiki=%s, librarian=%s, total=%d",
        "on" if channels.issue_tracker else "off",
        "on" if channels.wiki else "off",
        "on" if channels.librarian else "off",
        len(tools),
    )


__all__ = [
    "build_checkpointer",
    "build_event_bus",
    "log_runtime_ready",
    "mask_dsn",
]
