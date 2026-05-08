# Primary 에이전트

프로젝트 매니저(PM) 역할. 사용자와 기획을 협의하고 PRD 를 정제하며 전체 흐름을
관리한다. 전체 설계: [`docs/proposal/agents-roles.md`](../../docs/proposal/agents-roles.md).
런타임 전략: [`docs/agent-runtime.md`](../../docs/agent-runtime.md).

- 이슈: #6
- M2 스코프: 수신 → LLM 호출 → 응답. 외부 MCP / Librarian / 다른 에이전트 연동 없음.

---

## 디렉토리 구조

```
agents/primary/
├── Dockerfile                 # python:3.13-slim 기반 이미지
├── pyproject.toml             # primary-agent 패키지 정의
├── config/
│   └── base.yaml              # role / persona / llm / a2a_peers / agent_card (이미지에 baked-in)
├── src/primary_agent/
│   ├── __init__.py
│   ├── graph.py               # LangGraph StateGraph (build_graph / build_llm / load_runtime_config)
│   └── server.py              # FastAPI — /healthz, /.well-known/agent-card.json, /a2a/{id}
└── README.md                  # 본 문서
```

Override config (API 키 등 환경 의존 값) 는 **레포 루트 `overrides/primary.yaml`** 로
별도 관리되며, compose 가 이를 컨테이너의
`/app/primary/config/override.yaml` 로 마운트한다 (gitignore 로 커밋 제외).

---

## 사전 준비

### 1. `.env` 준비
레포 루트에서:
```bash
cp .env.example .env
# .env 편집해서 ANTHROPIC_API_KEY 값을 채워넣는다
```

### 2. `overrides/primary.yaml` 준비
```bash
cp overrides/primary.yaml.example overrides/primary.yaml
# 필요하면 모델/온도/api_key 경로 조정 (기본은 ${ANTHROPIC_API_KEY} 참조)
```

---

## 로컬 dev (호스트, Docker 없이)

Postgres 없이 in-memory 로 빠르게 확인:

```bash
# ANTHROPIC_API_KEY 를 shell 에 주입
set -a && source .env && set +a

# uvicorn 실행 (--reload 로 코드 수정 시 자동 재시작)
uv run uvicorn primary_agent.server:app \
    --app-dir agents/primary/src \
    --host 127.0.0.1 --port 8001 --reload
```

그 후:
```bash
curl http://localhost:8001/.well-known/agent-card.json
curl -X POST http://localhost:8001/a2a/primary \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":"1","method":"SendMessage","params":{"message":{"messageId":"m1","role":"ROLE_USER","parts":[{"text":"안녕"}]}}}'
```

Postgres 연동까지 로컬에서 확인하려면:
```bash
# postgres 만 먼저 띄우기
docker compose up -d postgres postgres-init

# DATABASE_URI 를 export 후 uvicorn 재기동
export DATABASE_URI="postgres://devteam:devteam_postgres@localhost:5432/langgraph"
# (uvicorn 재시작)
```

---

## 프로덕션 (docker compose)

```bash
# 전체 스택 (infra + agents) 기동
docker compose --profile agents up -d --build

# 상태 확인
docker ps --filter "name=dev-team"

# 로그 (primary)
docker logs -f dev-team-primary
```

### 엔드포인트 (호스트 기준)

| 경로 | 호스트 URL |
|---|---|
| Liveness | `http://localhost:9001/healthz` |
| AgentCard | `http://localhost:9001/.well-known/agent-card.json` |
| A2A JSON-RPC | `POST http://localhost:9001/a2a/primary` |

### 검증

```bash
# AgentCard 포맷 확인
curl -sS http://localhost:9001/.well-known/agent-card.json | jq .

# 실제 LLM 대화
curl -sS -X POST http://localhost:9001/a2a/primary \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc":"2.0",
    "id":"verify-1",
    "method":"SendMessage",
    "params":{"message":{"messageId":"ITM-1","role":"ROLE_USER","parts":[{"text":"자기 소개 한 줄."}]}}
  }' | jq '.result.history[1].parts[0].text'

# 체크포인트 테이블 확인 (AsyncPostgresSaver 가 생성)
docker exec dev-team-postgres psql -U devteam -d langgraph -c "\dt"
```

정상이면:
- AgentCard `name == "primary"`, `skills[].id == "pm.discuss_plan"`, `capabilities.streaming == true`
- SendMessage `result.kind == "task"` · `result.status.state == "TASK_STATE_COMPLETED"`
- `\dt` 에 `checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, `checkpoint_migrations`

### SSE 스트리밍 (`SendStreamingMessage`)

토큰 단위로 실시간 수신하려면 `method` 를 바꾸고 `curl --no-buffer`:

```bash
curl -sS --no-buffer -X POST http://localhost:9001/a2a/primary \
  -H 'Content-Type: application/json' \
  -H 'Accept: text/event-stream' \
  -d '{
    "jsonrpc":"2.0","id":"s-1","method":"SendStreamingMessage",
    "params":{"message":{"messageId":"m1","role":"ROLE_USER",
              "parts":[{"text":"세 문장짜리 자기 소개."}]}}
  }'
```

수신 이벤트 순서:
1. `result.kind == "task"` · `status.state == "TASK_STATE_SUBMITTED"` (초기)
2. `result.kind == "artifact-update"` · `append=true, lastChunk=false` (토큰 chunk들)
3. `result.kind == "status-update"` · `state == "TASK_STATE_COMPLETED"` · `final=true` (마감)

오류 시 마지막 이벤트가 `status-update` + `state=TASK_STATE_FAILED` + 에러 메시지.

---

## 제약 (M2)

- 외부 PM MCP, Librarian 질의, 타 에이전트 A2A peer 호출 **미구현**
- 단일 skill (`pm.discuss_plan`) 만 선언
- SSE 스트리밍 / thread list API / run 관리 API 미구현 — 필요 시점에 추가

---

## 관련 문서

- [`docs/proposal/agents-roles.md`](../../docs/proposal/agents-roles.md) — Primary 역할 전체 설계 (entry point: [`docs/proposal-main.md`](../../docs/proposal-main.md))
- [`docs/agent-runtime.md`](../../docs/agent-runtime.md) — 공용 런타임/빌드 규약
- [`docs/infra-setup.md`](../../docs/infra-setup.md) — 인프라 (Neo4j/Postgres/Valkey) 기동 가이드
- [`shared/src/dev_team_shared/a2a/README.md`](../../shared/src/dev_team_shared/a2a/README.md) — AgentCard 및 A2A 타입
