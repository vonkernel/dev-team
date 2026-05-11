"""Chat session 인프라 (P/A 공통) — runtime / registry / TTL sweeper.

API 표면:
- `SessionRuntime` — 한 session 의 runtime 상태
- `SessionRegistry` — in-memory dict + TTL sweeper
- 기본 정책 상수

**Implementation detail 미노출**: `chat_event_buffer` 모듈의 `_ChatEventBuffer`
는 SessionRuntime 내부 자료구조 — 의도적으로 본 `__init__` 에서 export 안 함.
직접 접근이 필요한 경우 (예: 단위 테스트) `dev_team_shared.chat_protocol
.session.chat_event_buffer` 로 explicit import.
"""

from dev_team_shared.chat_protocol.session.registry import (
    DEFAULT_IDLE_TTL_S,
    DEFAULT_SWEEP_INTERVAL_S,
    SessionRegistry,
)
from dev_team_shared.chat_protocol.session.runtime import (
    DEFAULT_MAX_BACKLOG_MESSAGES,
    SessionRuntime,
)

__all__ = [
    "DEFAULT_IDLE_TTL_S",
    "DEFAULT_MAX_BACKLOG_MESSAGES",
    "DEFAULT_SWEEP_INTERVAL_S",
    "SessionRegistry",
    "SessionRuntime",
]
