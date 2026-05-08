# 프로젝트 구조

> 본 문서는 [`proposal-main.md`](../proposal-main.md) §7 에서 분리 (#66).
> 마지막 갱신: #75 PR 3 (2026-05) — 옛 구조 (`langgraph_base/`, agent별
> `extensions/`, `adapters/`, `broker/`, `mcp-servers/`) 가 실제 구현과
> 어긋나 있어 현 상태로 정합.

```
dev-team/
├── docs/
│   └── proposal/                  # 아키텍처 / 모델 / 워크플로 디자인 문서
│
├── shared/                        # 공통 파이썬 패키지 (모든 에이전트 / chronicler / UG 가 import)
│   ├── pyproject.toml             # 로컬 editable 설치
│   ├── CLAUDE.md                  # 서브패키지 추가 / 분류 규약 (Pattern A vs B)
│   └── src/dev_team_shared/
│       ├── a2a/                   # A2A v1.0 server / client / types
│       │   ├── server/
│       │   │   ├── graph_handlers/  # SendMessage / SendStreamingMessage handler + RPCContext / log_rpc
│       │   │   └── ...
│       │   ├── client.py
│       │   ├── decision.py        # A2A 응답 shape 결정 schema + LLM classify_response factory
│       │   ├── tracing.py         # X-A2A-Trace-Id 헤더
│       │   └── types.py           # Message / Part / TaskState 등
│       ├── agent_graph/           # LangGraph agent 그래프 building blocks (#75 PR 3)
│       │   └── react.py           # llm_call / tool_node / should_continue / serialize_tool_result
│       ├── config_loader/         # Role Config 로딩 (base + override 병합)
│       ├── doc_store/             # Doc Store MCP typed client (Pattern A)
│       ├── event_bus/             # Valkey Streams ABC + ValkeyEventBus + 11 events
│       ├── issue_tracker/         # IssueTracker MCP typed client (Pattern A)
│       ├── llm/                   # LangChain ChatModel factory + provider registry
│       ├── mcp_client/            # Streamable HTTP MCP client wrapper
│       └── wiki/                  # Wiki MCP typed client (Pattern A)
│
├── agents/                        # 에이전트 컨테이너 (각자 독립 빌드)
│   ├── primary/
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   ├── config/
│   │   │   ├── base.yaml          # Role Config (이미지에 baked-in) — persona / llm / mcp_servers / a2a_peers
│   │   │   └── override.yaml      # (선택) 호스트 마운트 — base 위에 부분 덮어쓰기
│   │   ├── resources/             # LLM 컨텍스트에 embed 되는 prompt 자료 (가이드 / 템플릿)
│   │   │   ├── issue-management-guide.md
│   │   │   └── wiki-authoring-guide.md
│   │   └── src/primary_agent/
│   │       ├── server.py          # FastAPI lifespan + A2A router include
│   │       ├── graph.py           # build_graph() — shared/agent_graph + a2a.decision building blocks 조립
│   │       ├── tools/             # 4 채널 LangChain tool (Doc Store / IssueTracker / Wiki / Librarian A2A)
│   │       ├── channels.py
│   │       ├── lifespan_helpers.py
│   │       └── settings.py
│   └── librarian/
│       ├── Dockerfile
│       ├── pyproject.toml
│       ├── config/base.yaml
│       └── src/librarian_agent/
│           ├── server.py
│           ├── graph.py           # 동일 패턴 (shared building blocks)
│           └── tools.py           # Doc Store read 도구 (자연어 검색 사서)
│   # M4+ : architect/, M5+ : engineer/, qa/ 추가 예정
│
├── overrides/                     # 호스트 마운트 override (시크릿 / 환경별)
│   ├── primary.yaml               # 예: ANTHROPIC_API_KEY 주입
│   └── librarian.yaml
│
├── user-gateway/                  # 사용자 facing — REST / SSE 중계 + FE
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── frontend/                  # React UI
│   └── src/user_gateway/
│       ├── routes.py              # /api/chat (POST + SSE 중계)
│       ├── event_publisher.py     # session.start / chat.append publish
│       ├── upstream.py            # A2AUpstream 어댑터
│       └── ...
│
├── chronicler/                    # 대화 이벤트 consumer (에이전트 아님, 경량)
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── CLAUDE.md
│   └── src/chronicler/
│       ├── main.py
│       ├── consumer.py            # Valkey Streams XREADGROUP + XACK
│       ├── handler.py             # event_type → processor dispatch (registry)
│       └── processors/            # 이벤트 type 별 strategy (chat / assignment / a2a 3 layer)
│
├── mcp/                           # 공유 MCP 서버 (각자 별 이미지)
│   ├── CLAUDE.md                  # MCP 서버 공통 규약 (thin bridge / Pydantic 직접 노출 등)
│   ├── doc-store/                 # PostgreSQL 기반 — sessions / chats / assignments / a2a_* / issues / wiki_pages
│   ├── issue-tracker/             # GitHub Issues + Projects v2 어댑터
│   └── wiki/                      # GitHub Wiki 어댑터
│
├── infra/
│   └── init/                      # 인프라 초기화 스크립트 (postgres init 등)
│
├── docker-compose.yml             # 전체 스택 오케스트레이션 (profile: mcp / agents)
└── CLAUDE.md                      # 프로젝트 일반 작업 규약 (root)
```

## 모듈 구조 원칙

- **에이전트별 독립 컨테이너** — 각자 `pyproject.toml` + `Dockerfile` 갖고 독립 빌드. 컨테이너 간 통신은 A2A (에이전트 간) / chat protocol (UG↔P/A) / MCP (도구 / 데이터 서비스).
- **`shared/` 공통 패키지** — typed MCP 클라이언트 (Pattern A), 인프로세스 라이브러리 (Pattern B). 분류 규약: [`shared/CLAUDE.md`](../../shared/CLAUDE.md).
- **agent 별 차별화 지점**:
  | 차원 | 위치 |
  |---|---|
  | 정체성 / 책임 / 행동 원칙 | `config/base.yaml` 의 `persona` |
  | 도메인 워크플로 가이드 | `resources/*.md` |
  | 도구 구성 | `src/<name>/tools[.py 또는 /]` |
  | Graph 토폴로지 | `src/<name>/graph.py` 의 `build_graph()` (shared building blocks 조립) |
  | LLM / 연결 정보 | `config/base.yaml` 의 `llm`, `mcp_servers`, `a2a_peers` |
- **Engineer / QA (M5+)** — 모듈 하나를 specialty (be / fe / devops 등) 별 컨테이너로 기동 예정. config 가 specialty 별로 분리.
- **Role Config 로딩**: `config/base.yaml` (필수, 이미지 baked-in) + `overrides/<name>.yaml` (선택, 호스트 마운트). `shared/config_loader` 가 병합 + env 치환.
- **MCP 서버 (`mcp/`)** — 외부 도구 / 데이터 서비스의 thin bridge. 호출자 (LLM 에이전트) 의 도메인 추상은 LLM 이 결정. MCP 는 wire-level 통신만. 자세한 규약: [`mcp/CLAUDE.md`](../../mcp/CLAUDE.md).
- **Chronicler** — A2A / chat / assignment 이벤트의 consumer. 에이전트 아님 (LangGraph / LLM 미사용). Valkey Streams XREADGROUP → Doc Store MCP 적재.

**참고:** 본 구조는 `dev-team` 시스템 자체. **실제 개발 대상 프로젝트는 별도의 호스트 경로** (`${TARGET_PROJECT_PATH}`) 에서 각 에이전트 컨테이너에 `/workspace` 로 마운트.
