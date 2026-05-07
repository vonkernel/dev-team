# 기술 스택 상세

> 본 문서는 [`proposal-main.md`](../proposal-main.md) §6 에서 분리. (#66)

## 6.1. 에이전트 구성 컨셉 — Python + LangChain + LangGraph

본 시스템의 모든 에이전트는 **Python + LangChain + LangGraph** 의 3 layer 조합으로 구성된다. 이 조합이 "어떻게 사고하고 / 어떻게 행동하고 / 무엇을 기억하는가" 의 골격을 정의한다.

### 왜 Python?

LLM / 에이전트 / MCP 생태계의 1st-class 언어. LangGraph / LangChain / MCP SDK / 주요 어댑터 (Anthropic / OpenAI / Neo4j / asyncpg) 가 모두 Python 1차 지원. 여러 언어를 섞으면 통합 비용이 커지므로 한 언어로 통일.

### LangGraph — 사고의 흐름 (워크플로우 엔진 + 상태 머신)

LangGraph 는 에이전트의 사고를 **명시적인 graph (StateGraph)** 로 표현한다. 한 에이전트의 한 응답이 단일 LLM 호출이 아닌 **여러 단계의 노드 + 분기 + 루프** 로 펼쳐질 수 있다. 본 시스템에서 이 표현력이 핵심으로 활용되는 지점:

- **단계적 추론** — 수신 → 사고 → 도구 호출 → 검증 → 응답 같은 multi-step 패턴
- **분기 / 루프** — Architect 의 *메인 설계 → 검증 → 최종 컨펌 → (반려 시 재작업)* 같은 sub-agent 피드백 루프가 sub-graph 로 자연스럽게 표현 ([agents-roles](agents-roles.md) / [proposal-main §1.4](../proposal-main.md#14-에이전트-구성))
- **상태 영속 (체크포인트)** — 노드 사이마다 상태 스냅샷이 PostgreSQL 에 저장되어 프로세스 중단 / 재기동 / 사용자 인터럽션 (`TASK_STATE_INPUT_REQUIRED`) 후 **직전 체크포인트부터 이어서 진행** 가능. 장시간 자율 작업의 정상화 보장

본 시스템의 multi-agent 패턴은 **두 layer 로 분리** 된다:

- **Within-agent (LangGraph)** — 한 에이전트 안의 sub-graph 모듈들. 예: Architect 의 3-sub-agent 루프, Engineer 의 자체 설계-구현-검증 루프
- **Cross-agent (A2A)** — 별 컨테이너 간 통신 (§6.3). LangGraph 의 multi-agent 추상이 아닌 **별도의 표준 프로토콜** 위에 직접 구현 — 컨테이너 격리 / 언어 중립 / 외부 에이전트 합류 가능성 보존을 위해

### LangChain — LLM 추상화 (provider 교체 가능)

각 LangGraph 노드가 LLM 을 호출할 때 **LangChain 의 `BaseChatModel` 인터페이스** 를 통해 호출한다. config 의 `provider` + `model` 로 구현체 결정 — `ChatAnthropic` (Claude) / `ChatOpenAI` (GPT) / `ChatGoogleGenerativeAI` (Gemini) / 로컬 LLM (`ChatOllama` 등) 으로 자유로이 교체. 도구 호출 / 스트리밍 / structured output 같은 LLM 기능을 통일 인터페이스로 제공.

한 에이전트 안에서도 sub-agent 별로 다른 모델을 쓸 수 있다 — Architect 의 메인 설계는 `claude-opus-4-7`, 검증도 같은 모델, 최종 컨펌은 가벼운 `claude-sonnet-4-6` ([proposal-main §8 #25](../proposal-main.md#8-확정-사항-decisions-made)).

### 세 layer 의 결합 — 두뇌 / 손 / 기억

본 시스템 에이전트의 모든 동작은 다음 3 책임으로 분해된다:

| 레이어 | 책임 | 구현 |
|---|---|---|
| **두뇌** (사고) | 무엇을 할지 결정 | LangGraph 노드 안의 LangChain LLM 호출 |
| **손** (실행) | 결정한 것을 실행 | Code Agent (OpenCode CLI) 어댑터 / MCP 클라이언트 (도구 호출) |
| **기억** (영속) | 컨텍스트 유지 | LangGraph 체크포인터 (대화 / 작업 상태) + Atlas / Doc Store MCP (지식 자산) |

이 분리 덕에 Code Agent / LLM Provider / Atlas / Doc Store 모두 인터페이스 추상화가 가능 (§6.5 추상화 레이어).

> **상세 패키지 / 임포트 / 컨테이너 내부 와이어링** 은 본 문서의 범위가 아님. [`docs/agent-runtime.md` §1 런타임 스택](../agent-runtime.md) 참조.

## 6.2. 컨테이너 구성

```yaml
# 예시: docker-compose 구조
# ${TARGET_PROJECT_PATH} = 작업 대상 프로젝트의 호스트 경로
# 각 에이전트는 독립 모듈이며 각자 Dockerfile로 빌드 (공유 이미지 없음)
services:
  # --- 에이전트 (모듈별 독립 빌드, 공용 코드는 shared/ 에서 import) ---
  # 기본 config은 이미지에 baked-in. 필요 시 override.yaml만 마운트하여 일부 필드 덮어쓰기.
  primary:
    build: ./agents/primary
    volumes:
      - ./overrides/primary.yaml:/app/config.override.yaml   # (선택) override
    depends_on: [doc-db-mcp, external-pm-mcp, valkey]

  architect:
    build: ./agents/architect
    volumes:
      - ./overrides/architect.yaml:/app/config.override.yaml
      - ${TARGET_PROJECT_PATH}:/workspace   # 코드 읽기 + docs/design/ 쓰기

  librarian:
    build: ./agents/librarian
    volumes:
      - ./overrides/librarian.yaml:/app/config.override.yaml

  # BE 페어 — specialty는 CONFIG_PROFILE 환경변수로 선택
  eng-be:
    build: ./agents/engineer
    environment:
      - CONFIG_PROFILE=be       # 이미지 내부의 configs/be.yaml을 base로 사용
    volumes:
      - ./overrides/eng-be.yaml:/app/config.override.yaml
      - ${TARGET_PROJECT_PATH}:/workspace

  qa-be:
    build: ./agents/qa
    environment:
      - CONFIG_PROFILE=be
    volumes:
      - ./overrides/qa-be.yaml:/app/config.override.yaml
      - ${TARGET_PROJECT_PATH}:/workspace

  # FE 페어
  eng-fe:
    build: ./agents/engineer
    environment:
      - CONFIG_PROFILE=fe
    volumes:
      - ./overrides/eng-fe.yaml:/app/config.override.yaml
      - ${TARGET_PROJECT_PATH}:/workspace

  qa-fe:
    build: ./agents/qa
    environment:
      - CONFIG_PROFILE=fe
    volumes:
      - ./overrides/qa-fe.yaml:/app/config.override.yaml
      - ${TARGET_PROJECT_PATH}:/workspace

  # --- User Gateway (사용자 접점) ---
  user-gateway:
    build: ./user-gateway
    ports: ["8080:8080"]              # 사용자 UI 접속용
    depends_on: [primary, architect]

  # --- 공유 MCP 서버 (별도 이미지) ---
  atlas-mcp:
    build: ./mcp-servers/atlas
    depends_on: [neo4j]

  doc-db-mcp:
    build: ./mcp-servers/doc-db
    depends_on: [postgres]

  external-pm-mcp:
    build: ./mcp-servers/external-pm   # 기본 구현: GitHub Wiki + Issue
    environment:
      - GITHUB_TOKEN=${GITHUB_TOKEN}
      - GITHUB_REPO=${GITHUB_REPO}

  # --- 데이터베이스 ---
  neo4j:
    image: neo4j:5
    ports: ["7474:7474", "7687:7687"]

  # 단일 Postgres 인스턴스에 2개 DB 분리 운영 (§6.5 참조)
  #   - langgraph : langgraph-checkpoint-postgres (AsyncPostgresSaver) 전용
  #   - dev_team  : 애플리케이션 (Doc Store) — 정형 RDB 스키마 + 일부 JSONB
  postgres:
    image: postgres:17
    ports: ["5432:5432"]

  # --- 대화 기록 파이프라인 (Valkey Streams + Chronicler) ---
  valkey:
    image: valkey/valkey:9
    command: ["valkey-server", "--appendonly", "yes"]

  chronicler:
    build: ./chronicler
    depends_on: [valkey, doc-db-mcp]
    environment:
      - VALKEY_URL=redis://valkey:6379
      - STREAM_NAME=a2a-events
      - CONSUMER_GROUP=chronicler-cg
      - DOC_DB_MCP_URL=http://doc-db-mcp:8080
```

**에이전트 빌드 원칙:**
- 역할당 **독립 디렉토리 + 독립 Dockerfile** — 각자 python + langgraph 앱으로 빌드
- Engineer/QA처럼 specialty만 다른 경우, 하나의 모듈을 여러 specialty 컨테이너로 띄움 (config 파일로 분화)
- 공통 코드(A2A 클라이언트/서버, MCP 클라이언트, Role Config 로더, 이벤트 publish 등)는 `shared/` 패키지에서 import하여 중복 최소화

**API Key 주입 원칙:**
- `.env` 파일에 `ANTHROPIC_API_KEY`, `GITHUB_TOKEN` 등을 정의 (docker-compose가 자동 로드)
- 각 에이전트 서비스의 `environment` 블록에 필요한 env를 명시적으로 선언 (최소 권한 원칙)
- Override yaml의 `${ANTHROPIC_API_KEY}` 같은 참조는 로더가 기동 시 치환
- `.env`는 `.gitignore`에 포함, 리포지토리에는 `.env.example` 템플릿만 커밋

```yaml
# 예시: agents/primary 서비스에 API key env 주입
primary:
  build: ./agents/primary
  env_file: [.env]
  environment:
    - ANTHROPIC_API_KEY       # .env에서 로드된 값을 컨테이너에 전달
```

**볼륨 마운트 원칙:**
- 코드 작업이 필요한 에이전트(Architect, Engineer, QA)는 **같은 호스트 경로**를 `/workspace`에 마운트 → 동일 코드베이스 공유
- 쓰기 범위는 에이전트 내부 로직 + Role Config에서 허용 디렉토리를 명시하여 제한
- Primary와 Librarian은 코드베이스를 마운트하지 않음 (불필요)

## 6.3. A2A 통신 (A2A Protocol v1.0)

에이전트 간 통신은 **[A2A Protocol v1.0](https://a2a-protocol.org/latest/)** (Linux Foundation 표준) 을 따른다. 구현은 **자체 FastAPI** 라우트 (`shared.a2a` 패키지) 위에 직접 구성 — 각 에이전트가 `/a2a/{role}` 엔드포인트로 JSON-RPC 2.0 메서드를 노출하고 `/.well-known/agent-card.json` 으로 Agent Card 를 공개. 별도의 A2A Gateway 컨테이너 / 게이트웨이 라이브러리는 불필요. 자세한 와이어링은 [`agent-runtime.md`](../agent-runtime.md) 참조.

> **이력**: 초기 후보였던 `langgraph-api` (구 v0.4.x 의 내장 A2A 서버) 는 `langgraph-storage-postgres` (상업 라이센스) 의존 때문에 OSS 자체 호스팅 경로와 충돌해 **#6 에서 폐기**. 현재는 `langgraph-checkpoint-postgres` (체크포인터) + 자체 FastAPI A2A 라우트 조합.

**JSON 직렬화 규약** ([spec §5.5](https://a2a-protocol.org/latest/specification/)): 필드는 **camelCase**, enum은 proto 이름 그대로 SCREAMING_SNAKE_CASE 문자열 (예: `"TASK_STATE_SUBMITTED"`, `"ROLE_USER"`).

### 지원 RPC 메서드 (JSON-RPC 2.0)

A2A v1.0 스펙의 공식 메서드명은 PascalCase:

| 메서드 | 설명 | 우리 용도 |
|--------|------|----------|
| `SendMessage` | 동기 요청-응답. 짧은 작업은 `Message` 직접 반환, 긴 작업은 `Task` 객체 반환 | 일반 에이전트 간 대화 (기본 경로) |
| `SendStreamingMessage` | SSE 스트리밍 — 초기 `Task`/`Message` 후 `TaskStatusUpdateEvent` / `TaskArtifactUpdateEvent` 전달 | **User Gateway ↔ Primary** 사용자 채팅 실시간 렌더링, 장시간 응답 점진 전달 |
| `GetTask` | 이전 task 상태·아티팩트·history 조회 | 비동기 긴 작업 상태 추적 |

> **이력 (참고):** `langgraph-api` 초기 버전의 내장 A2A 엔드포인트는 구(舊) 명세 기반 `message/send` / `message/stream` / `tasks/get` (슬래시 형식) 메서드명을 노출했다. 본 시스템은 `langgraph-api` 폐기 (#6) 후 자체 FastAPI 위에 v1.0 PascalCase 메서드명을 직접 구현 — 의존 없는 깔끔한 정렬.

### Task Lifecycle

[spec §4.1.1 TaskState](https://a2a-protocol.org/latest/specification/) enum 값(JSON 직렬화 값) 과 우리 시나리오 매핑:

| State (JSON 값) | 분류 | 우리 시스템 매핑 예 |
|----------------|------|-------------------|
| `TASK_STATE_SUBMITTED` | 진행 | 태스크 배분 직후 |
| `TASK_STATE_WORKING` | 진행 | Engineer 구현 중, QA 테스트 중 |
| `TASK_STATE_INPUT_REQUIRED` | **인터럽트** | Engineer 이 Architect 에게 설계 수정 건의 후 응답 대기 / 사용자 기술 조율 요청 대기 / 다자간 논의 소집 중 |
| `TASK_STATE_AUTH_REQUIRED` | 인터럽트 | (예비) 외부 시스템 인증 요구 시 |
| `TASK_STATE_COMPLETED` | 종단 | 정상 종료 |
| `TASK_STATE_FAILED` | 종단 | 빌드 실패, 예외 등 |
| `TASK_STATE_CANCELED` | 종단 | 요청자 취소 |
| `TASK_STATE_REJECTED` | 종단 | 상위 설계 반려 등 |

`TASK_STATE_INPUT_REQUIRED` 를 적극 활용하여 LangGraph 내부 상태가 외부 인터럽션 때문에 블로킹되지 않도록 한다.

### Agent Card

각 에이전트는 `/.well-known/agent-card.json` 경로에 **AgentCard** 를 노출한다. Role Config 의 공개 가능한 부분을 [spec §4.4.1](https://a2a-protocol.org/latest/specification/) 정의에 맞는 JSON 포맷으로 제공:

```json
{
  "name": "architect",
  "description": "시스템 아키텍트 — OO 설계 주도, 설계 결정권 보유",
  "version": "0.1.0",
  "supportedInterfaces": [
    {
      "url": "http://architect:9000/a2a/architect",
      "protocolBinding": "JSONRPC"
    }
  ],
  "provider": {
    "organization": "dev-team",
    "url": "https://github.com/vonkernel/dev-team"
  },
  "capabilities": {
    "streaming": true,
    "pushNotifications": false,
    "extendedAgentCard": false
  },
  "defaultInputModes": ["text/plain"],
  "defaultOutputModes": ["text/plain"],
  "skills": [
    {
      "id": "design_proposal",
      "name": "OO 설계안 생성",
      "description": "요구사항·코드 제약을 고려한 복수 설계안 도출",
      "tags": ["architecture", "design"]
    },
    {
      "id": "code_review",
      "name": "Quality Gate 코드 검수",
      "description": "Eng 의 diff 와 설계 의도 합치 여부 검증",
      "tags": ["review"]
    }
  ]
}
```

**필수 필드**(스펙 `REQUIRED`): `name`, `description`, `supportedInterfaces[]`, `version`, `capabilities`, `defaultInputModes[]`, `defaultOutputModes[]`, `skills[]`. 각 `skill` 은 `id`, `name`, `description`, `tags[]` 가 필수.

**시그니처**(`signatures[]`, [spec §4.4.7](https://a2a-protocol.org/latest/specification/) AgentCardSignature) 는 미채택 — 부록 참조.

### A2A 메시지 포맷 (JSON-RPC 2.0)

`SendMessage` 요청 예:

```json
{
  "jsonrpc": "2.0",
  "id": "req-001",
  "method": "SendMessage",
  "params": {
    "message": {
      "messageId": "ITM-42",
      "role": "ROLE_USER",
      "parts": [
        {
          "text": "결제 모듈 설계안 검토 부탁드립니다.",
          "mediaType": "text/plain"
        }
      ],
      "contextId": "SES-xxx",
      "taskId": "TASK-001"
    }
  }
}
```

- `messageId`: 발신자가 생성하는 고유 ID (UUID 권장) — **필수**
- `role`: `ROLE_USER` 또는 `ROLE_AGENT` — **필수**
- `parts[]`: 컨텐츠 컨테이너 — **필수**. 각 `Part` 는 `text` / `raw` / `url` / `data` 중 하나 (oneof) + 선택적 `mediaType`, `filename`, `metadata`
- `contextId`: 대화 문맥 (우리 시스템의 Session 매핑)
- `taskId`: 기존 Task 에 붙이는 경우 지정
- `referenceTaskIds[]`: 관련 Task 들 참조 (다자간 논의 등에서 활용 가능)

응답은 짧은 작업이면 `Message`, 긴 작업이면 `Task`(`status.state`가 `TASK_STATE_SUBMITTED`/`TASK_STATE_WORKING`)를 반환. 후자는 `GetTask` 폴링 또는 `SendStreamingMessage` SSE 구독으로 진행.

## 6.4. MCP 연동 계획

MCP 서버는 두 종류로 나뉜다:

**공유 MCP 서버 (N:1, 에이전트 외부):**
- Atlas MCP — 코드-과업 관계 그래프 접근, FIFO 큐잉으로 쓰기 직렬 처리
- Doc Store MCP — 실행 기록/의사결정 근거 접근, FIFO 큐잉으로 쓰기 직렬 처리

**역할별 MCP 도구 (1:1, 에이전트 내부):**

| 에이전트 | Shared Memory MCP (write) | Shared Memory MCP (read) | External PM MCP | 역할별 MCP 도구 |
|----------|:------------------------:|:-----------------------:|:---------------:|---------------|
| Primary | **O** (직접 — wiki_pages / issues) | O (직접) + 정보 검색·외부 조사 → Librarian | **O** (단독 창구 — IssueTracker / Wiki) | — |
| Architect | **O** (직접 — atlas / wiki_pages ADR 등) | O (직접) + 정보 검색·외부 조사 → Librarian | X (Primary 에게 위임) | 코드 읽기/검색, 리뷰 도구 |
| Librarian | minimal (M4+ 옵션 C 시 색인 추천만) | O — 사서 (정보 검색 + 외부 리소스 조사) | X | 없음 |
| Engineer:* | **O** (직접 — atlas 색인) | O (직접) + 정보 검색·외부 조사 → Librarian | X (Architect→Primary) | 코드 편집/빌드/테스트 |
| QA:* | **O** (직접 — wiki_pages / 테스트 결과) | O (직접) + 정보 검색·외부 조사 → Librarian | X (Architect→Primary) | 테스트 실행/리포트 |

**정정된 원칙** ([architecture-shared-memory](architecture-shared-memory.md) 분담 모델 참조):
- **write 직접**: 자기 도메인 데이터는 자기 MCP 호출 — schema 노출 / dispatch 비용 ↓ / traceability ↑
- **정보 검색 사서 (Librarian)**: DB 안의 자연어 / 교차 쿼리는 Librarian 의 LLM 매핑 활용
- **외부 리소스 조사 전담 (Librarian)**: 라이브러리 docs / URL / web search 는 Librarian 단독 ([architecture-external-research](architecture-external-research.md))
- **외부 PM 단독 창구 (Primary)**: Doc Store ↔ GitHub Issues / Wiki sync 는 Primary 가 직접 IssueTracker / Wiki MCP 호출. Architect / Engineer / QA 가 외부 반영 필요하면 Architect→Primary 위임.

## 6.5. 추상화 레이어 (OCP 원칙)

시스템의 핵심 외부 의존성은 **인터페이스 계약**을 먼저 정의하고, 실제 구현체는 교체 가능하도록 구성한다. **초기 구현체**는 아래 "기본 구현" 컬럼을 따르되, 인터페이스를 통해 추후 다른 구현을 추가할 수 있도록 한다(Open-Closed Principle).

| 추상화 대상 | 인터페이스 목적 | 기본 구현 | 대체 가능 예시 | 연동 방식 |
|------------|---------------|----------|--------------|---------|
| **Code Agent** | 코드 편집/빌드/테스트 실행 | OpenCode CLI | Claude Code CLI, Aider CLI, Cursor CLI | 에이전트 내부 어댑터 |
| **Atlas** | OO 구조(Interface/Class/PublicMethod) 저장/조회 | Neo4j | ArangoDB, JanusGraph, Neptune | 공유 MCP 서버 |
| **Doc Store** | PRD/문서/대화(Task/Session/Item) 저장/조회 | **PostgreSQL** (정형 RDB + JSONB 보조) | CouchDB, MongoDB, Elasticsearch | 공유 MCP 서버 |
| **External PM Tool** | PRD/태스크 외부 공유 및 동기화 | GitHub Wiki + GitHub Issue | Jira, Confluence, Linear, Notion | **공유 MCP 서버** |
| **LLM Provider** | 추론 엔진 | Claude API (ChatAnthropic) | OpenAI / Gemini / 로컬 LLM (ChatOpenAI, ChatGoogleGenerativeAI 등) | **LangChain `BaseChatModel` 인터페이스 사용** — config의 `provider` + `model`로 구현체 선택 |

**DB/외부 도구 연동 통일:** Shared Memory(Graph/Doc Store)뿐 아니라 External PM Tool도 **공유 MCP 서버**로 래핑한다. 에이전트 입장에서는 모든 외부 시스템이 MCP라는 동일 인터페이스로 추상화되며, 구현체 교체는 MCP 서버를 바꿔치기하는 것으로 끝난다.

### 저장소 선택 맥락 — 왜 PostgreSQL 인가 (Doc Store 기본 구현)

초기 설계에서는 Doc Store 의 기본 구현을 MongoDB 로 두었으나, 다음 이유로 **PostgreSQL** (정형 RDB 스키마, 일부 필드 JSONB) 로 전환한다 (이슈 #20):

1. **워크플로우 엔진의 본질적 요구 — 영속 체크포인트** — LangGraph 는 에이전트 워크플로우 엔진이므로 **노드 실행 사이사이에 상태 스냅샷(체크포인트) 을 저장** 해야 한다. 이 영속 저장이 있어야 프로세스 중단 / 재기동 / 오류 복구 시 **직전 체크포인트부터 이어서 진행** 할 수 있다 (장시간 에이전트 작업의 정상화 보장). 본 시스템은 `langgraph-checkpoint-postgres` 의 `AsyncPostgresSaver` 를 그래프 컴파일 시 wiring — `DATABASE_URI` 가 필수. 별도 Doc Store 를 두면 저장소 종류가 중복되고 운영 부담이 증가한다.
2. **정형 RDB + JSONB 보조** — 5 collection 모두 정형 스키마 (UUID PK / FK / CHECK / UNIQUE / 정형 컬럼) + JSONB 는 `metadata` / `external_refs` / `agent_items.content` / `wiki_pages.structured` 같은 일부 자유 필드만. 관계 무결성 + 전형적 RDB 도구 (트랜잭션 / 외래키 / 인덱스) 그대로 + JSONB 의 스키마리스 유연성도 확보.
3. **관계형 보증과의 양립** — PRD 와 Task, Session 과 Item 간에는 명확한 관계가 존재하므로, 트랜잭션/외래키/조인을 활용할 수 있으면 무결성 유지가 쉬워진다. JSONB 는 관계형 기반 위에서 보조 데이터를 얹어 두 관점을 모두 수용한다.
4. **운영 단순화** — 저장소 종류를 하나 줄여 백업/모니터링/마이그레이션 관리 대상 감소.

운영 형태는 **단일 Postgres 인스턴스 + 2개 DB 분리** 다:

| DB | 소유자 | 용도 |
|---|---|---|
| `langgraph` | `langgraph-checkpoint-postgres` (AsyncPostgresSaver) | 체크포인트, 스레드, 런, 태스크 상태. **라이브러리가 직접 스키마/마이그레이션 관리** |
| `dev_team` | 애플리케이션 (Doc Store MCP) | wiki_pages / issues / agent_tasks / agent_sessions / agent_items. 우리가 스키마 설계·관리 |

같은 DB 에 섞지 않는 이유: `langgraph-checkpoint-postgres` 버전업 시 자체 마이그레이션이 애플리케이션 테이블을 건드릴 위험 제거 + 권한/백업 경계 분리. 인스턴스는 하나라 운영 복잡도는 거의 증가하지 않는다.

`Doc Store` 라는 **추상화 인터페이스 자체는 유지** 되므로, 향후 MongoDB / CouchDB / Elasticsearch 등 다른 document-oriented 구현체로 교체하고 싶어지면 Doc Store MCP 서버 구현체만 바꿔치우면 된다.

### 인터페이스 예시

**CodeAgent 인터페이스 (의사 코드):**
```python
class CodeAgent(ABC):
    @abstractmethod
    def edit_file(self, path: str, instruction: str) -> Diff: ...
    @abstractmethod
    def run_build(self) -> BuildResult: ...
    @abstractmethod
    def run_tests(self, pattern: str = "*") -> TestResult: ...

class OpenCodeCliAgent(CodeAgent): ...
class ClaudeCodeCliAgent(CodeAgent): ...
class AiderCliAgent(CodeAgent): ...
```

**External PM MCP 서버 (도구 시그니처 예시):**
```yaml
# MCP 서버가 노출하는 도구들
tools:
  - name: upsert_prd
    inputs: { prd: PRD }
    outputs: { ref: PmDocRef }
  - name: upsert_task
    inputs: { task: Task }
    outputs: { ref: PmDocRef }
  - name: update_status
    inputs: { ref: PmDocRef, status: Status }
  - name: get_issue
    inputs: { ref: PmDocRef }
    outputs: { issue: Issue }
```

구현체는 `github-wiki-issue-mcp`, `jira-confluence-mcp`, `linear-mcp` 등으로 별도 컨테이너로 빌드된다. 에이전트는 config에서 MCP URL만 지정하면 된다.

### 구현체 선택 메커니즘

- Role Config의 각 추상화 필드(`code_agent.type`, `external_pm.type` 등)에서 구현체 이름을 지정
- 에이전트 기동 시 팩토리가 해당 구현체를 로드
- 새 구현체를 추가하려면 인터페이스를 구현하고 팩토리에 등록만 하면 됨 (기존 코드 수정 불필요 = OCP)
