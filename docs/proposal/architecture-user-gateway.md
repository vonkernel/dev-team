# User Gateway

> 본 문서는 [`proposal-main.md`](../proposal-main.md) §2.2 에서 분리. (#66)

사용자는 에이전트에 직접 접속하지 않고 **User Gateway**를 통해 소통한다. User Gateway는 사용자 측 UI(웹/CLI/채팅)와 내부 A2A 네트워크를 연결하는 **중계 계층**이다.

**역할:**
- 사용자 채팅 입력을 A2A `SendMessage` 또는 `SendStreamingMessage` 로 변환하여 P 또는 A 에게 전달
- **SSE streaming** 활용 — 에이전트 응답(LLM 토큰, 중간 상태)을 실시간 UI 로 렌더링
- P/A 가 사용자에게 전달할 메시지를 수신하여 UI 로 렌더링
- 긴 작업은 `Task` 객체로 반환받아 `GetTask` 로 상태 추적 (`TASK_STATE_INPUT_REQUIRED` 상태면 사용자 입력 유도 UI 표시)
- 사용자 인증/세션 관리
- 사용자 개입 이벤트도 일반 A2A 이벤트와 동일하게 Valkey Streams 로 publish → Chronicler 가 Doc Store 에 기록

**라우팅 규칙:**
- 기획 관련 대화 (요구사항, PRD, 일정 등) → P로 전달
- 기술 관련 대화 (설계, 기술 선택, 구현 조율) → A로 전달
- 사용자가 명시적으로 대상을 지정하면 그쪽으로 전달
- 사용자의 초기 요청은 기본적으로 P로 전달
