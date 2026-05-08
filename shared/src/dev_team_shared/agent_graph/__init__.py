"""LangGraph agent 그래프의 공통 building blocks.

각 agent 의 graph.py 가 본 패키지의 factory / helper 를 import 해 자기 그래프를
조립한다 (agent-specific 추가 노드 / topology 자유). 모든 agent 가 같은 패턴
을 강제하지 않고 building block 만 제공해 시각적 명확성 + DRY 양립.

서브모듈:
- `react` — ReAct 패턴 building blocks (llm_call / tool_node / should_continue
  / serialize_tool_result)

protocol-level 노드 (예: A2A response shape 결정 = `make_classify_response_node`)
는 본 패키지가 아닌 해당 protocol 모듈 (`shared/a2a/decision.py`) 에 위치.
graph 조립 시 양쪽 모두 import 해 사용.
"""

from dev_team_shared.agent_graph.react import (
    make_llm_call_node,
    make_tool_node,
    serialize_tool_result,
    should_continue_react,
)

__all__ = [
    "make_llm_call_node",
    "make_tool_node",
    "serialize_tool_result",
    "should_continue_react",
]
