# A2A 서브 패키지 설계 노트

본 문서는 `dev_team_shared.a2a` 모듈의 **설계 의도**와 **사용 방식**을 정리한다.
API 레퍼런스가 아니라 "왜 이렇게 만들었는가"를 남기는 문서다.

관련 스펙: [A2A Protocol v1.0 공식 문서](https://a2a-protocol.org/latest/specification/)

---

## 1. 모듈 구성

| 파일 | 책임 |
|---|---|
| `types.py` | A2A 메시지/태스크 타입 (`Message`, `Part`, `Role`, `TaskState`) |
| `agent_card.py` | AgentCard 및 하위 모델 + `build_agent_card()` 빌더 |
| `client.py` | 다른 에이전트의 A2A 엔드포인트를 호출하는 JSON-RPC 클라이언트 |

서버 본체(`/a2a/{assistant_id}` 라우트)는 `langgraph-api` 가 내장 제공하므로 본 패키지에는
포함하지 않는다. 본 패키지는 **"A2A 를 말하기 위한 공통 어휘"** 만 담는다.

---

## 2. AgentCard 개념

AgentCard 는 A2A 프로토콜에서 에이전트의 **공개 자기소개서** 역할을 하는 JSON 문서다.
spec §4.4.1 에 따라 모든 에이전트는 `/.well-known/agent-card.json` 경로에 이를 노출해야 한다.

클라이언트(다른 에이전트 또는 오케스트레이터) 는 통신 **전에** 이 카드를 먼저 읽어서:

1. **"어디 있어? 어떤 프로토콜로 말해?"** → `supportedInterfaces`
2. **"뭘 할 수 있어?"** → `skills`
3. **"streaming / push 알림 지원해?"** → `capabilities`

를 파악한 뒤 실제 요청을 보낸다.

### 2.1. 서브 모델 요약

| 모델 | 역할 | spec |
|---|---|---|
| `AgentCard` | 루트 문서. 아래 모든 것을 묶음. | §4.4.1 |
| `AgentProvider` | 운영 주체 (organization, url) | §4.4.2 |
| `AgentCapabilities` | streaming / pushNotifications / extendedAgentCard 지원 플래그 | §4.4.3 |
| `AgentSkill` | 에이전트가 처리 가능한 작업 단위 (id/name/description/tags 필수) | §4.4.5 |
| `AgentInterface` | 물리적 접속 정보 (url + protocolBinding) | §4.4.6 |

### 2.2. AgentSkill 이 왜 중요한가

Primary(Orchestrator) 가 "어떤 작업을 누구에게 보낼지" 결정할 때
각 peer 의 `skills[].tags` 와 `description` 을 본다.
즉 AgentSkill 은 마이크로서비스의 API 엔드포인트 목록과 비슷한
**기계 판독 가능한 계약(contract)** 역할을 한다.

---

## 3. 설계 철학: 상속이 아니라 설정 주입

### 3.1. AgentCard 모델은 DTO 다 — 상속 대상이 아님

`AgentCard`, `AgentSkill` 등은 Pydantic `BaseModel` 기반의 **값 객체(DTO)** 다.
동작 로직이 없고, 스펙이 정한 필드 구조도 변할 일이 없다.

각 에이전트가 `class EngineerAgentCard(AgentCard): ...` 로 서브클래싱하는 것은
**안티패턴**이다:

- 에이전트마다 달라지는 것은 **값**(skills, url, capabilities)이지 **구조**가 아니다.
- 상속으로 풀면 Pydantic 스키마 정의가 에이전트 코드에 흩어진다 → SRP 위반.
- A2A spec 이 고정된 구조를 요구하므로 확장 포인트가 없다.

### 3.2. 대신 "Config → 빌더 → 인스턴스" 패턴

```
Role Config (YAML)
    │
    ▼
build_agent_card(config)        ← 공통 함수 (shared 패키지)
    │
    ▼
AgentCard 인스턴스 (메모리 상주)
    │
    ▼
GET /.well-known/agent-card.json
```

각 에이전트가 하는 일:

1. Role Config YAML 에 자기 `role`, `persona`, `agent_card` 블록 작성
2. 부팅 시 `build_agent_card(loaded_config)` 한 번 호출
3. 결과 인스턴스를 `/.well-known/agent-card.json` 라우트에 바인딩

에이전트 쪽 코드에 AgentCard 관련 클래스 정의는 한 줄도 없다.

---

## 4. 런타임 흐름: 공통 이미지, 서로 다른 카드

```
┌─ 빌드 타임 (Docker image) ────────────────────────────────────┐
│  모든 에이전트가 동일한 이미지                                  │
│  - shared 패키지 (AgentCard 모델, build_agent_card)            │
│  - 런타임 코드                                                  │
└───────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─ 부팅 타임 (컨테이너마다 다른 Config 마운트) ──────────────────┐
│                                                                │
│   engineer 컨테이너           architect 컨테이너              │
│   ├─ /config/base.yaml        ├─ /config/base.yaml            │
│   └─ /config/override.yaml    └─ /config/override.yaml        │
│           │                           │                        │
│           ▼                           ▼                        │
│     load_config(...)             load_config(...)              │
│           │                           │                        │
│           ▼                           ▼                        │
│     build_agent_card(cfg)        build_agent_card(cfg)         │
│           │                           │                        │
│           ▼                           ▼                        │
│     AgentCard 인스턴스 A         AgentCard 인스턴스 B          │
│     (engineer:backend)           (architect)                   │
│           │                           │                        │
│           ▼                           ▼                        │
│    GET /.well-known/agent-card.json (각자 다른 JSON)           │
└───────────────────────────────────────────────────────────────┘
```

**핵심 3가지**:

1. **이미지는 하나, 인스턴스는 N개** — 빌드 산출물에는 AgentCard 값이 박히지 않는다.
2. **한 번만 만들어 재사용** — 부팅 시 단 한 번 build, 결과를 `app.state` 등에 저장.
3. **Config 가 다르면 카드가 다르다** — 동일 이미지에서도 Config 마운트만 바꾸면 완전히 다른 에이전트가 된다.

---

## 5. 사용 예시

### 5.1. Role Config 측 (YAML)

```yaml
role: engineer
specialty: backend
persona: |
  You are a backend engineer specializing in Python services.

agent_card:
  url: http://engineer:9000/a2a/engineer
  protocol_binding: JSONRPC
  version: 0.1.0
  capabilities:
    streaming: true
    pushNotifications: false
  default_input_modes: [text/plain]
  default_output_modes: [text/plain]
  skills:
    - id: implement-feature
      name: Feature Implementation
      description: Implements a software feature given a spec and file context.
      tags: [python, backend, implementation]
  provider:
    organization: dev-team
    url: https://github.com/example/dev-team
```

### 5.2. 에이전트 부팅 코드 (의사 코드)

```python
from dev_team_shared.config_loader import load_config
from dev_team_shared.a2a import build_agent_card

config = load_config("config/base.yaml", "config/override.yaml")
agent_card = build_agent_card(config)

@app.get("/.well-known/agent-card.json")
def serve_card() -> dict:
    return agent_card.model_dump(by_alias=True, exclude_none=True)
```

`model_dump(by_alias=True, exclude_none=True)` 로 직렬화하는 이유:

- **by_alias**: Python snake_case → A2A spec 이 요구하는 camelCase 로 변환
- **exclude_none**: 선택 필드가 `null` 로 튀어나가지 않도록 제거

---

## 6. 향후 확장 지점

현재 범위에 포함되지 않은 spec 항목들 (필요해질 때 추가):

| 영역 | spec | 현재 상태 |
|---|---|---|
| AgentCard 서명 (`signatures[]`) | §4.4.8 | 제외 — 초기 범위에서 생략 |
| 확장 카드 (Authenticated Extended Card) | §4.4.1 (extendedAgentCard) | 플래그만 정의, 실제 엔드포인트 미구현 |
| Security schemes | §4.4.4 | 미구현 — 내부망 기준 초기에는 불필요 |
| gRPC 바인딩 | §3.1 | JSONRPC 만 지원 |

---

## 7. 레이어 책임 분리 요약

| 계층 | 공통화 방식 | 위치 |
|---|---|---|
| 데이터 스키마 (AgentCard 등) | 단일 모델 + 빌더 함수 | `shared/a2a/agent_card.py` |
| 메시지/태스크 타입 | Pydantic 모델 + StrEnum | `shared/a2a/types.py` |
| 아웃바운드 호출 | JSON-RPC 클라이언트 | `shared/a2a/client.py` |
| 서버 라우트 (`/a2a/{id}`) | langgraph-api 내장 | (외부 의존성) |
| 에이전트 런타임 공통 로직 | 베이스 클래스 (예정) | 각 에이전트 앱 또는 별도 베이스 모듈 |

**"정보 공개(AgentCard)"는 설정 주입으로, "공통 동작 로직"은 베이스 클래스로**
— 두 관심사가 서로 다른 레이어에 분리되어 있다.
