# User Gateway

> 본 문서는 [`proposal-main.md`](../proposal-main.md) §2.2 에서 분리. (#66)
> 두 tier 분리 / chat protocol 도입 반영 (#75).

사용자는 에이전트에 직접 접속하지 않고 **User Gateway** 를 통해 소통한다.
User Gateway 는 사용자 측 UI (웹) 와 내부 에이전트들을 연결하는 **얇은
인터페이스 / routing 계층**이다.

UG ↔ Primary / Architect 통신은 **A2A 가 아니라 별도 chat protocol** ([architecture-chat-protocol](architecture-chat-protocol.md))
— REST POST + 영속 SSE per session. 사용자 ↔ 에이전트는 에이전트 간 통신과
다른 영역이라 자체 어휘 (Session / Chat / Assignment) 로 정의하는 게 의미상
깔끔하다 (#75).

**역할:**
- **session 생성 / 발급** (`POST /api/sessions`) — session 은 사용자 주도
  개념이므로 UG 가 session_id (UUID) 발급. `session.start` publish 도 UG 가
  담당 (1회만, 생성 시점에)
- FE 의 채팅 입력 (`POST /api/chat`) 을 받아 session 의 `agent_endpoint` 컬럼
  보고 해당 agent 의 internal chat endpoint 로 forward
- agent 의 응답 chunk 를 영속 SSE 채널 (`GET /api/stream?session_id=X`) 로
  FE 에 push
- 사용자 인증 / 세션 관리 (server-side `sessions` 컬렉션)
- chat lifecycle 이벤트 (`session.start` / `chat.append` role=user) 를
  Valkey Streams 로 publish — Chronicler 가 Doc Store 에 적재. session 은
  종료 개념이 없으므로 `session.end` 발화 없음 (대화창 metaphor — 사용자가
  언제든 재개 가능). agent 의 발화 (`chat.append` role=agent) 는 agent 자기가
  publish (UG 가 대신 publish 안 함)

**의미 판단 / batch merge / cancel intent / stop 처리는 UG 책임 아님** —
agent (Primary / Architect) 의 LLM 영역. UG 는 인터페이스만, agent 가 자기
큐 + persona 가이드로 처리 (#72).

**라우팅 규칙 (session 기반):**
- 사용자가 새 chat 시작 (UI "새 대화" 버튼) → FE 가 `POST /api/sessions
  {agent_endpoint}` 호출 → UG 가 session_id 발급 + `session.start` publish
  + `sessions` row 생성 (CHR 가 영속화) → 응답에 session_id
- 이후 그 session 의 모든 chat 은 같은 agent_endpoint 로 forward
- M3 의 기본은 Primary endpoint (M4+ 에서 Architect 직접 chat 추가)

**Endpoint 매트릭스:**

| Endpoint | 위치 | 호출자 | 책임 |
|---|---|---|---|
| `POST /api/sessions` | UG | FE | 새 chat session 생성. body: `{agent_endpoint}`. 응답: 201 `{session_id, agent_endpoint, started_at}` |
| `GET /api/sessions` | UG | FE | chat list 조회 (사이드바 hydrate) |
| `GET /api/history?session_id=X` | UG | FE | 리프레시 / 새 탭 시 chats hydrate |
| `POST /api/chat` | UG | FE | 사용자 발화 제출. body: `{session_id, text}`. 응답: 202 ack |
| `GET /api/stream?session_id=X` | UG | FE | 영속 SSE 채널 |
| `POST /chat/send` (내부) | 각 agent (P / A) | UG | UG 가 forward |
| `GET /chat/stream?session_id=X` (내부) | 각 agent (P / A) | UG | UG 가 SSE 중계 |

**FE 측 영속 (localStorage):**
```
activeSessionId   ← 현재 열려 있는 chat 의 session_id
sessions          ← chat list cache (id, title, agent_endpoint, last_chat_at)
```

server 의 `sessions` 테이블이 source of truth. localStorage 는 chat list
표시 / active session 빠른 전환을 위한 cache.
