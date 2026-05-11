"""Agent / 서비스 lifespan 의 공용 wiring helper (Pattern B — in-process library).

FastAPI lifespan 본문에서 인프라 wiring 디테일을 분리. `AsyncExitStack` 에
cleanup 등록 패턴을 표준화 — caller (lifespan) 은 stack 만 넘기고 helper 가
resource 인스턴스화 + cleanup 등록 모두 책임.

각 agent (Primary / Librarian / 향후 Architect / Engineer / QA) 가 동일
패턴 — 중복 제거 (DRY) + 일관 동작 보장.

서브모듈:
- `event_bus` — `build_event_bus` (Valkey 활성 시 EventBus 인스턴스화, graceful fallback)
- `checkpointer` — `build_checkpointer` (Postgres / in-memory)

DSN 보안 helper `mask_dsn` 은 lifespan 책임 아님 — `dev_team_shared.utils` 참조.

agent 별 특수 helper (예: Primary 의 `log_runtime_ready`, Librarian 의
`build_doc_store_client` 등) 는 각 agent 의 `lifespan_helpers.py` 에 남김 —
shared 는 *모든 agent 공통* 만.
"""

from dev_team_shared.lifespan.checkpointer import build_checkpointer
from dev_team_shared.lifespan.event_bus import build_event_bus

__all__ = [
    "build_checkpointer",
    "build_event_bus",
]
