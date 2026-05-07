# shared 패키지 — 작업 규약

`shared/src/dev_team_shared/` 의 모든 서브패키지가 따르는 골격. AI 에이전트 /
인간 모두 새 서브패키지 추가 시 본 문서 + root [`CLAUDE.md`](../CLAUDE.md) 의
"모듈 코드 구조" 함께 따른다.

---

## 1. 두 가지 패턴

shared 의 서브패키지는 책임에 따라 두 패턴 중 하나로 분류된다. 새 모듈 추가
시 어느 패턴인지 먼저 결정하고 진행.

### Pattern A — Out-of-process service SDK

외부 서비스 (보통 MCP 서버) 의 **consumer-side typed wrapper**. 호출자는
**모든 에이전트** (P / A / ENG / QA / CHR / L) — 자기 도메인 데이터를 MCP
직접 write / read ([architecture-shared-memory](../docs/proposal/architecture-shared-memory.md) 참조). 실 어댑터 /
backend 호출 코드는 shared 가 아닌 별 모듈 (`mcp/<name>/` 등) 안.

**책임**:
- typed client (도구 호출 → Pydantic 검증)
- 공유 schemas (server / client 양쪽이 import)
- 도구명 상수 (`tool_names.py`)

**예**:
- [`doc_store/`](src/dev_team_shared/doc_store/) — `DocStoreClient` (server: `mcp/doc-store/`)
- [`issue_tracker/`](src/dev_team_shared/issue_tracker/) — `IssueTrackerClient` (server: `mcp/issue-tracker/`)
- [`wiki/`](src/dev_team_shared/wiki/) — `WikiClient` (server: `mcp/wiki/`)

**구조**:
```
shared/src/dev_team_shared/<name>/
├── __init__.py            # re-export
├── client.py              # <Name>Client (composition: sub-clients)
├── _ops_client.py         # 도메인별 sub-client (ISP)
├── schemas/               # server / client 단일 정의 (mcp/<name>/ 가 import)
└── tool_names.py          # 도구명 상수
```

본 SDK 가 호출하는 backend 의 ABC / concrete adapter 는 `mcp/<name>/src/<name>_mcp/adapters/`
에 위치 (mcp/CLAUDE.md §2.2). shared 에 backend 코드 두지 않는다.

### Pattern B — In-process infra library

LangGraph 노드 / lifespan 에서 **인프로세스 라이브러리로 직접 호출**되는 인프라.
MCP 서버로 분리할 이유 없음 (round-trip + serialization 오버헤드만 늘고, 도구
catalog 같은 MCP 의 이점이 인프로세스 호출엔 부적합).

**책임**:
- ABC + factory + concrete 구현체 모두 shared 에 직접
- 다른 서브패키지 / 에이전트가 import 해 인스턴스 생성

**예**:
- [`a2a/`](src/dev_team_shared/a2a/) — A2A 프로토콜 server / client (FastAPI / langgraph 노드 안)
- [`event_bus/`](src/dev_team_shared/event_bus/) — Valkey Streams 기반 publish / consume
- [`mcp_client/`](src/dev_team_shared/mcp_client/) — Streamable HTTP MCP 클라이언트 wrapper
- [`llm/`](src/dev_team_shared/llm/) — LangChain ChatModel factory + provider registry
- [`config_loader/`](src/dev_team_shared/config_loader/) — Role config 로딩

**구조** (LLM 예):
```
shared/src/dev_team_shared/<name>/
├── __init__.py            # re-export
├── factory.py             # 진입점 (config → 인스턴스)
├── providers/             # concrete (필요 시)
│   ├── __init__.py        # side-effect import (registry 자가 등록)
│   └── <provider>.py
└── ... (도메인별)
```

---

## 2. 패턴 선택 가이드

| 질문 | A | B |
|---|---|---|
| 별 컨테이너로 분리되는 service 인가? | ✅ | ❌ |
| LangGraph 노드 / lifespan 에서 직접 import 해 사용? | ❌ (typed client 만) | ✅ |
| 호출 비용에 round-trip / serialization 부담 가능? | ✅ | ❌ (인프로세스 직접) |
| 다른 언어 / 외부 시스템에서도 호출 필요? | ✅ (MCP 표준) | ❌ |

**대원칙**: 외부 도구 / 데이터 서비스는 MCP 채널 (Pattern A). 인프로세스
유틸리티 / 프로토콜 wrapper / LLM 호출 같은 라이브러리는 직접 (Pattern B).

새 모듈이 어느 쪽인지 모호하면 사용자 컨펌 후 진행.

---

## 3. 현재 서브패키지 분류

| 서브패키지 | 패턴 | 비고 |
|---|---|---|
| `a2a/` | B | FastAPI 라우터 + JSON-RPC + SSE wrapper |
| `config_loader/` | B | Role config / overrides 로딩 |
| `doc_store/` | A | server: `mcp/doc-store/` |
| `event_bus/` | B | Valkey Streams ABC + concrete |
| `issue_tracker/` | A | server: `mcp/issue-tracker/` |
| `llm/` | B | LangChain ChatModel factory |
| `mcp_client/` | B | Streamable HTTP MCP 클라이언트 |
| `wiki/` | A | server: `mcp/wiki/` |

---

## 4. 새 서브패키지 추가 절차

- [ ] **이슈 + 컨펌** — 패턴 (A/B) 결정 + 사용자 합의
- [ ] **패턴 A 의 경우**: server 측 (`mcp/<name>/`) 와 같이 디자인 — 두 PR 또는
  한 PR 분리 commit
- [ ] **본 문서 §3 표 갱신** — 새 서브패키지 + 패턴 분류
- [ ] **`shared/src/dev_team_shared/<name>/__init__.py`** 만들고 export
- [ ] **`shared/tests/`** 단위 테스트 (외부 의존 없는 부분)
- [ ] **import 경로 일관** — `from dev_team_shared.<name> import ...` (1단계)

---

## 5. 절대 금지

- **`adapters/`** 같은 categorical wrapper 디렉터리 신설 — 도메인 1단계 유지
- **Pattern A 인데 backend / concrete adapter 가 shared 에 박힘** — `mcp/<name>/`
  로 옮길 것 (thin bridge 원칙 + module 격리)
- **Pattern B 인데 별 컨테이너로 분리** — 인프로세스 호출 의도 위반

---

## 6. 관련 문서

- root [`CLAUDE.md`](../CLAUDE.md) — "모듈 코드 구조" / "에이전트 ↔ 외부 도구
  운영 원칙" / "통신 프로토콜 우선순위"
- [`mcp/CLAUDE.md`](../mcp/CLAUDE.md) §0 / §2.2 — Pattern A 의 server 측 규약
