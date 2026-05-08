"""A2A Protocol v1.0 통합 레이어.

서버 본체는 `langgraph-api` 가 내장 제공 (`/a2a/{assistant_id}`).
본 모듈은 다음을 담당:

- `AgentCard` 빌더 — Role Config 에서 `/.well-known/agent-card.json` 응답을 만든다.
- `A2AClient` — 다른 에이전트의 A2A 엔드포인트를 호출하기 위한 경량 JSON-RPC 2.0 클라이언트.
- Task 상태 상수 / Message·Part 타입 정의.
"""

from dev_team_shared.a2a.agent_card import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    build_agent_card,
)
from dev_team_shared.a2a.client import A2AClient, A2AClientError
from dev_team_shared.a2a.decision import (
    DEFAULT_RESPONSE_DECISION_PROMPT,
    A2AResponseDecision,
)
from dev_team_shared.a2a.tracing import TRACE_ID_HEADER
from dev_team_shared.a2a.types import Message, Part, TaskState

__all__ = [
    "A2AClient",
    "A2AClientError",
    "A2AResponseDecision",
    "AgentCapabilities",
    "AgentCard",
    "AgentSkill",
    "DEFAULT_RESPONSE_DECISION_PROMPT",
    "Message",
    "Part",
    "TRACE_ID_HEADER",
    "TaskState",
    "build_agent_card",
]
