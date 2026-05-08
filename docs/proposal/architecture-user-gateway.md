# User Gateway

> 본 문서는 [`proposal-main.md`](../proposal-main.md) §2.2 에서 분리. (#66)
> 두 tier 분리 / chat protocol 도입 반영 (#75).

사용자는 에이전트에 직접 접속하지 않고 **User Gateway** 를 통해 소통한다.
User Gateway 는 사용자 측 UI (웹) 와 내부 에이전트들을 연결하는 **얇은
인터페이스 / routing 계층**이다.

UG ↔ Primary / Architect 통신은 **A2A 가 아니라 별 chat protocol** ([architecture-chat-protocol](architecture-chat-protocol.md))
— REST POST + 영속 SSE per session. A2A 의 Task 어휘는 task 위임 / 협상 의도라
사용자와의 자연 chat 에는 부적합한 mismatch 가 있어 분리 (#75).

**역할:**
- FE 의 채팅 입력 (`POST /api/chat`) 을 받아 session 의 `agent_endpoint` 컬럼
  보고 해당 agent 의 internal chat endpoint 로 forward
- agent 의 응답 chunk 를 영속 SSE 채널 (`GET /api/stream?session_id=X`) 로
  FE 에 push
- 사용자 인증 / 세션 관리 (server-side `sessions` 컬렉션)
- chat lifecycle 이벤트 (chat.session.start / chat.append / chat.session.end)
  를 Valkey Streams 로 publish — Chronicler 가 Doc Store 에 적재

**의미 판단 / batch merge / cancel intent / stop 처리는 UG 책임 아님** —
agent (Primary / Architect) 의 LLM 영역. UG 는 인터페이스만, agent 가 자기
큐 + persona 가이드로 처리 (#72).

**라우팅 규칙 (session 기반):**
- 사용자가 새 chat 시작할 때 UI 에서 endpoint 선택 (Primary / Architect)
  → server 에 `sessions` row 생성 (`agent_endpoint` 컬럼 채워짐)
- 이후 그 session 의 모든 chat 은 같은 agent_endpoint 로 forward
- M3 의 기본은 Primary endpoint (M4+ 에서 Architect 직접 chat 추가)

**Endpoint 매트릭스:**

| Endpoint | 위치 | 호출자 |
|---|---|---|
| `POST /api/chat` | UG | FE |
| `GET /api/stream?session_id=X` | UG | FE |
| `GET /api/history?session_id=X` | UG | FE (리프레시 / 새 탭 시 hydrate) |
| `GET /api/sessions` | UG | FE (사이드바 chat list) |
| `POST /chat/send` (내부) | 각 agent (P / A) | UG |
| `GET /chat/stream?session_id=X` (내부) | 각 agent (P / A) | UG |

**FE 측 영속 (localStorage):**
```
activeSessionId   ← 현재 열려 있는 chat 의 session_id
sessions          ← 사이드바 cache (id, title, agent_endpoint, last_chat_at)
```

server 의 `sessions` 테이블이 source of truth. localStorage 는 사이드바
표시 / active session 빠른 전환을 위한 cache.
