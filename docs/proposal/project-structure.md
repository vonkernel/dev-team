# 프로젝트 구조 (예상)

> 본 문서는 [`proposal-main.md`](../proposal-main.md) §7 에서 분리. (#66)

```
dev-team/
├── docs/
│   ├── proposal-draft.md          # 본 기획서
│   └── architecture/              # 아키텍처 상세 문서
│
├── shared/                        # 공통 파이썬 패키지 (모든 에이전트가 import)
│   ├── pyproject.toml             # 로컬 editable 설치로 각 에이전트가 의존
│   └── src/dev_team_shared/
│       ├── langgraph_base/        # 공통 베이스 그래프 (수신→사고→행동→검증→응답)
│       ├── a2a/                   # A2A 서버/클라이언트 공통 구현
│       ├── mcp_client/            # MCP 클라이언트 초기화 유틸
│       ├── broker/                # Valkey Streams publish 헬퍼
│       ├── adapters/              # 추상화 인터페이스 + 구현체 (OCP)
│       │   ├── code_agent/        # OpenCode, Claude Code, Aider...
│       │   └── llm/               # Claude, OpenAI, Gemini...
│       ├── config_loader/         # Role Config 로더/스키마
│       ├── factory/               # adapter 팩토리
│       └── models/                # 공통 데이터 모델 (A2A 메시지, 이벤트, PRD 등)
│
├── agents/                        # 에이전트 모듈 (각자 독립 빌드)
│   ├── primary/
│   │   ├── Dockerfile
│   │   ├── pyproject.toml         # shared를 의존성으로 포함
│   │   ├── src/primary_agent/
│   │   │   ├── main.py
│   │   │   └── extensions/        # P 전용 서브그래프 (prd_authoring, external_pm_sync 등)
│   │   └── config.yaml            # Role Config
│   ├── architect/
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   ├── src/architect_agent/
│   │   │   ├── main.py
│   │   │   └── extensions/        # 3-서브 에이전트 루프, multi_proposal 등
│   │   └── config.yaml
│   ├── librarian/
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   ├── src/librarian_agent/
│   │   │   ├── main.py
│   │   │   └── extensions/        # diff_indexing, nl_query_answering
│   │   └── config.yaml
│   ├── engineer/                  # 모듈 하나를 specialty별 컨테이너로 기동
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   ├── src/engineer_agent/
│   │   │   ├── main.py
│   │   │   └── extensions/        # self_design_loop, design_escalation, diff_delivery
│   │   └── configs/               # 기본(baked-in) config — 이미지에 포함
│   │       ├── be.yaml
│   │       └── fe.yaml
│   └── qa/
│       ├── Dockerfile
│       ├── pyproject.toml
│       ├── src/qa_agent/
│       │   ├── main.py
│       │   └── extensions/        # independent_test_authoring, build_and_test_execution
│       └── configs/               # 기본(baked-in) config — 이미지에 포함
│           ├── be.yaml
│           └── fe.yaml
│
├── overrides/                     # (선택) 환경/운영별 override config 파일 (마운트용)
│   ├── primary.yaml               # 예: dev 환경 모델 downgrade
│   ├── eng-be.yaml
│   └── qa-be.yaml
│
├── user-gateway/                  # 사용자 UI + A2A 중계 서버
│   ├── Dockerfile
│   └── src/
├── chronicler/                    # 대화 로그 Consumer (에이전트 아님, 경량 모듈)
│   ├── Dockerfile
│   └── src/
│       └── main.py                # Valkey Streams 구독 → Doc DB MCP 저장
├── mcp-servers/                   # 공유 MCP 서버 (각각 별도 이미지 빌드)
│   ├── atlas/                  # Atlas MCP (기본: Neo4j)
│   ├── doc-db/                    # Doc Store MCP (기본: PostgreSQL + JSONB)
│   └── external-pm/               # External PM MCP (기본: GitHub Wiki+Issue)
│
├── infra/
│   ├── docker-compose.yml         # 컨테이너 오케스트레이션
│   └── configs/                   # 환경별 설정
└── tests/
    ├── integration/               # 에이전트 간 통합 테스트
    └── e2e/                       # 전체 워크플로우 E2E 테스트
```

**모듈 구조 원칙:**
- **에이전트별 독립 모듈** — 각자 pyproject.toml과 Dockerfile을 갖고 독립 빌드됨
- **`shared/` 공통 패키지** — LangGraph 베이스, A2A, MCP, Broker, Adapters 등 공통 로직을 모아두고 각 에이전트가 editable 의존성으로 import
- **Role Config는 각 모듈 내부**에 위치 (`agents/{role}/config.yaml` 또는 specialty별 여러 개)
- **Engineer, QA는 모듈 하나**로 개발하되 specialty별로 config를 분리하여 서로 다른 컨테이너로 기동

**참고:** 이 구조는 `dev-team` 시스템 자체의 구조이며, **실제 개발 대상 프로젝트는 별도의 호스트 경로**(`${TARGET_PROJECT_PATH}`)에서 각 에이전트 컨테이너에 `/workspace`로 마운트된다.
