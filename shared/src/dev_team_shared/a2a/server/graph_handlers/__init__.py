"""LangGraph 기반 에이전트용 A2A 메서드 핸들러.

`request.app.state.graph` 에 Compiled LangGraph 가 세팅되어 있다고 가정.
각 에이전트의 `server.py` 가 lifespan 에서 그래프 / agent_card 를 준비한 뒤
아래 핸들러를 `make_a2a_router(handlers=[...])` 로 등록하면 된다.

한 RPC 호출은 식별자 묶음(`RPCContext`) + lifecycle 스코프(`log_rpc`) 위에서
흐른다. 핸들러는 ctx 를 만들고 lifecycle 스코프 안에서 graph 를 호출한 뒤,
그 결과를 A2A Task / Event 모델로 조립(`factories`)해 envelope 헬퍼
(`envelope`)로 직렬화해 내보낸다. 스트리밍 경로는 `stream` 모듈이
graph.astream 을 SSE 라인으로 번역하면서 client disconnect 폴링과 keepalive
sentinel 처리를 함께 수행한다.

서브모듈 구성:

  config            env 기반 자원 관리 튜닝 (timeout / keepalive)
  rpc               RPCContext + log_rpc
  parse             요청 파싱 / LLM 응답 텍스트 추출
  factories         A2A Task / 이벤트 모델 조립 + 에러 텍스트
  envelope          JSON-RPC / SSE envelope 직렬화
  stream            graph.astream → SSE 라인 번역
  send_message      GraphSendMessageHandler (단방향)
  send_streaming    GraphSendStreamingMessageHandler (SSE)

SSE 자원 관리 정책 (#23, S1~S4) 은 `docs/sse-connection.md` 참조.
"""

from dev_team_shared.a2a.server.graph_handlers.send_message import (
    GraphSendMessageHandler,
)
from dev_team_shared.a2a.server.graph_handlers.send_streaming import (
    GraphSendStreamingMessageHandler,
)

__all__ = [
    "GraphSendMessageHandler",
    "GraphSendStreamingMessageHandler",
]
