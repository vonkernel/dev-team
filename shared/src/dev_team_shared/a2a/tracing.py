"""A2A 호출 간 trace ID 전파 규약.

`contextId` 는 한 에이전트 boundary 안의 대화 식별자 (spec §6). 시스템 전체
요청을 묶어 추적하려면 별도의 traceId 가 필요하다. 본 모듈은 그 규약을 정의
한다.

규약 요약:
- wire 위치: HTTP 헤더 `X-A2A-Trace-Id`
- 부재 시: 서버가 새로 발급 (`uuid4`). UG / 외부 진입점에서 누락돼도 시스템
  안에서 일관 추적.
- 운반 책임: 클라이언트 (`A2AClient`) 가 송신, 서버 (`make_a2a_router`) 가
  수신 후 `request.state.trace_id` 로 보관.
- 위임 시: Primary 등 위임자가 받은 traceId 를 자기 클라이언트 호출에
  forward → 트리 전체가 같은 trace 로 묶임 (별도 contextId 와는 독립).

참고: 추후 OpenTelemetry `traceparent` 헤더로 교체 / 병행 가능. 그 시점에는
본 모듈이 두 헤더를 모두 인식하도록 확장.
"""

from __future__ import annotations

from typing import Final

TRACE_ID_HEADER: Final[str] = "X-A2A-Trace-Id"
"""A2A trace ID 운반에 쓰는 HTTP 헤더 이름."""


__all__ = ["TRACE_ID_HEADER"]
