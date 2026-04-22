# 에이전트 런타임 / 빌드 전략

본 문서는 **LangGraph 기반 에이전트를 어떻게 개발 · 빌드 · 실행하는가** 에 대한
프로젝트 차원 결정 사항을 기록한다. 모든 에이전트(Primary, Architect, Engineer, ...)
가 공통으로 따르는 규약이다.

- 최초 작성 이슈: #18
- 주요 개정 이슈: #6 — langgraph-api 의존 제거, 자체 FastAPI 경로로 전환
- 관련 문서: [proposal.md](./proposal.md), [infra-setup.md](./infra-setup.md)

---

## 1. 런타임 스택

각 에이전트 컨테이너 안의 파이썬 스택은 다음 요소로 구성된다 — 전부 **OSS**.

| 레이어 | 패키지 | 역할 |
|---|---|---|
| 워크플로우 엔진 | `langgraph` | StateGraph / 노드 / 엣지 / 체크포인팅 계약 |
| LLM 어댑터 | `langchain-anthropic` (+ LangChain core) | `BaseChatModel` 구현체 |
| 영속 체크포인터 | `langgraph-checkpoint-postgres` | `AsyncPostgresSaver` — 체크포인트/스레드 영속 |
| HTTP 서버 | `fastapi` + `uvicorn[standard]` | A2A 엔드포인트 호스팅 |
| A2A 프로토콜 타입 | `shared.a2a` (자체 구현) | Message / Part / Role, AgentCard 빌더, JSON-RPC 클라이언트 |

> **주의** — 프로젝트 초기에 후보였던 `langgraph-api` / `langgraph-cli` 는 **사용하지 않는다**.
> 이유는 §10 회고 참조. 핵심은 langchain/langgraph-api 베이스 이미지가 상업 배포용
> `langgraph-storage-postgres` (라이센스 필요) 에 묶여 있어 OSS 자체 호스팅 경로와
> 충돌한다는 것. 대신 우리가 직접 FastAPI 로 A2A 라우트를 구성하고
> `langgraph-checkpoint-postgres` 를 `graph.compile(checkpointer=...)` 에 wiring 한다.

```mermaid
flowchart TB
    Ext["외부 클라이언트<br/>(다른 에이전트, User Gateway)"]
    Api["FastAPI 서버 (primary_agent.server:app)<br/>• /.well-known/agent-card.json<br/>• /a2a/{assistant_id} (JSON-RPC 2.0)<br/>• /healthz"]
    Graph["LangGraph 워크플로우<br/>• StateGraph (messages reducer)<br/>• LLM 호출 노드"]
    Saver["AsyncPostgresSaver<br/>(체크포인트 테이블)"]
    PG[("PostgreSQL — langgraph DB")]

    Ext -->|HTTP / JSON-RPC| Api
    Api -->|graph.ainvoke| Graph
    Graph -.persist.-> Saver
    Saver -.->|SQL| PG
```

---

## 2. 개발 루프 (호스트, Docker 없이)

```bash
# shell 에 ANTHROPIC_API_KEY 주입 (.env 의 값을 source)
set -a && source .env && set +a

# 자동 리로드로 실행
uv run uvicorn primary_agent.server:app \
    --app-dir agents/primary/src \
    --host 127.0.0.1 --port 8001 --reload
```

DATABASE_URI 를 생략하면 **in-memory** 로 동작 (재기동 시 체크포인트 소실). 대화 흐름
만 빠르게 확인하려는 단계에 적합.

Postgres 와도 붙여서 검증하고 싶으면 `infra/docker-compose.yml` 의 postgres 만
먼저 띄우고 (`docker compose ... up -d postgres postgres-init`), shell 에서
`DATABASE_URI=postgres://devteam:devteam_postgres@localhost:5432/langgraph` 를 export.

---

## 3. 프로덕션 컨테이너 이미지

### 3.1. 디렉토리 구조 가정

```
dev-team/
├── shared/              ← 공통 패키지 (모든 에이전트가 import)
└── agents/
    ├── primary/
    │   ├── Dockerfile
    │   ├── pyproject.toml
    │   ├── config/base.yaml
    │   └── src/primary_agent/{graph,server}.py
    └── ...
```

이미지 안에는 `shared/` + `agents/{role}/` 둘 다 들어가야 한다.

### 3.2. 베이스 이미지: `python:3.13-slim`

**라이센스 이슈가 없는** 깨끗한 파이썬 베이스. 이전에 검토했던
`langchain/langgraph-api:*` 는 상업 배포용 postgres runtime 이 ENV 로 박혀 있어
기동 시 LangGraph Cloud 라이센스를 요구 — OSS 경로에 부적합.

### 3.3. Dockerfile 표준 레이아웃

```dockerfile
FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
 && rm -rf /var/lib/apt/lists/*

ENV PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# 1) shared 먼저 설치 (에이전트 패키지의 dev-team-shared 의존 해소)
COPY shared /app/shared
RUN pip install -e /app/shared

# 2) 에이전트 패키지 설치
#    [tool.uv.sources] (workspace 참조) 블록 제거 — Docker 안엔 workspace 없음
COPY agents/<role> /app/<role>
RUN sed -i '/^\[tool\.uv\.sources\]/,/^$/d' /app/<role>/pyproject.toml \
 && pip install -e /app/<role>

WORKDIR /app/<role>
EXPOSE 8000
CMD ["uvicorn", "<role>_agent.server:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 3.4. 빌드 (레포 루트에서)

```bash
docker build -f agents/primary/Dockerfile -t dev-team/primary:latest .
```

빌드 context 는 **레포 루트** 여야 `shared/` 와 `agents/primary/` 둘 다 COPY 대상에
들어간다.

---

## 4. 영속 체크포인팅 (AsyncPostgresSaver)

각 에이전트의 `server.py::lifespan` 이 다음을 수행:

```python
database_uri = os.environ.get("DATABASE_URI")
if database_uri:
    async with AsyncPostgresSaver.from_conn_string(database_uri) as checkpointer:
        await checkpointer.setup()          # idempotent schema/table 생성
        graph = build_graph(persona=..., llm=..., checkpointer=checkpointer)
        ...
else:
    graph = build_graph(persona=..., llm=..., checkpointer=None)  # in-memory
```

생성되는 테이블 (Postgres `langgraph` DB 의 `public` 스키마):
- `checkpoints` — 노드 단위 상태 스냅샷
- `checkpoint_blobs` — 대용량 state 분리 저장
- `checkpoint_writes` — 부분 업데이트(reducer diff)
- `checkpoint_migrations` — 스키마 버전

`AsyncPostgresSaver.setup()` 은 **idempotent** — 재기동마다 안전하게 호출 가능.

---

## 5. A2A 엔드포인트 (자체 구현)

각 에이전트 FastAPI 서버가 다음을 노출한다. 구현은 `<role>_agent/server.py`.

| 메서드 | 경로 | 내용 |
|---|---|---|
| `GET` | `/.well-known/agent-card.json` | A2A spec §4.4 에이전트 자기소개서. `shared.a2a.build_agent_card(config)` 로 빌드. |
| `POST` | `/a2a/{assistant_id}` | JSON-RPC 2.0. 현재 구현 메서드: `SendMessage`. |
| `GET` | `/healthz` | liveness. |

### assistant_id 규약

우리 자체 구현이므로 **assistant_id = graph 이름(역할명)** 을 그대로 사용:
`/a2a/primary`, `/a2a/architect` 등. (초기 문서에서 langgraph-api 의 UUID 기반
규칙을 언급했던 부분은 구현 경로 변경으로 무효.)

### SendMessage 처리 흐름

1. A2A `Message` → text part 추출 → `HumanMessage` 1개로 변환
2. `graph.ainvoke({"messages": [human]}, config={"configurable": {"thread_id": contextId}})`
3. 결과의 마지막 `AIMessage` 를 뽑아 A2A `Message(role=ROLE_AGENT)` 로 포장
4. `TASK_STATE_COMPLETED` 와 함께 `history` 반환

실패 시엔 `TASK_STATE_FAILED` + 에러 메시지 포함 `status.message` 반환.

---

## 6. 기동 후 검증

```bash
# 1) AgentCard
curl -sS http://localhost:9001/.well-known/agent-card.json | jq .

# 2) A2A SendMessage
curl -sS -X POST http://localhost:9001/a2a/primary \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc":"2.0",
    "id":"verify-1",
    "method":"SendMessage",
    "params":{"message":{"messageId":"ITM-1","role":"ROLE_USER","parts":[{"text":"hi"}]}}
  }' | jq .

# 3) 체크포인트 테이블 존재 확인
docker exec dev-team-postgres psql -U devteam -d langgraph -c "\dt"
```

**정상 판정 기준**:
- AgentCard 가 `name`, `supportedInterfaces[].url`, `capabilities`, `skills[]` 반환
- SendMessage → `result.task.status.state == "TASK_STATE_COMPLETED"`, `history[1].role == "ROLE_AGENT"` 에 LLM 응답 텍스트
- `\dt` 에 `checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, `checkpoint_migrations` 4개 존재

---

## 7. 주의할 환경변수

| 변수 | 용도 | 설정 시점 |
|---|---|---|
| `ANTHROPIC_API_KEY` | LLM 호출용 | 컨테이너 env (레포 루트 `.env` 에서 전달) |
| `DATABASE_URI` | Postgres DSN (`postgres://user:pass@postgres:5432/langgraph`). 미설정 시 in-memory. | 컨테이너 env |

---

## 8. AgentCard 커스터마이즈

langgraph-api 를 쓰던 시절과 달리 **AgentCard 를 완전히 우리가 제어** 한다.
`shared/a2a/agent_card.py` 의 `build_agent_card(config)` 가 Role Config 의
`agent_card` 블록을 소비해 A2A `AgentCard` 객체를 반환, FastAPI 라우트에서
`model_dump(by_alias=True, exclude_none=True)` 로 직렬화.

`agent_card` 블록 구조 (config/base.yaml):
```yaml
agent_card:
  version: "0.1"
  url: http://primary:8000/a2a/primary
  protocol_binding: JSONRPC
  capabilities:
    streaming: false
    pushNotifications: false
  default_input_modes: [text/plain]
  default_output_modes: [text/plain]
  provider:
    organization: dev-team
    url: https://github.com/vonkernel/dev-team
  skills:
    - id: pm.discuss_plan
      name: Planning Discussion
      description: ...
      tags: [pm, planning, chat]
```

**스킬 세분화는 자유** — JSON-RPC 메서드 단위로 분기 가능한 자체 구현이므로.
현 M2 는 skill 1개만 선언.

---

## 9. 결정 요약표

| 항목 | 결정 |
|---|---|
| 베이스 이미지 | `python:3.13-slim` |
| HTTP 서버 | FastAPI + uvicorn (자체 구현) |
| A2A 엔드포인트 | `shared.a2a` + 각 agent 의 `server.py` 로 자체 구현 |
| 영속 저장소 | OSS `langgraph-checkpoint-postgres` (`AsyncPostgresSaver`) — `graph.compile(checkpointer=...)` |
| 이미지 빌드 | `docker build -f agents/<role>/Dockerfile -t dev-team/<role>:latest .` (레포 루트에서) |
| 컨테이너 기동 | compose `agents` profile 또는 `docker run` 단독. CMD = `uvicorn <role>_agent.server:app` |
| 개발 루프 | `uvicorn ... --reload` (호스트에서) |
| assistant_id | graph 이름(역할명) 그대로 — UUID 변환 없음 |
| 우리가 작성하는 것 | `graph.py`, `server.py`, `config.yaml`, `Dockerfile` |

---

## 10. 회고 — 왜 langgraph-api 를 쓰지 않는가

초기 조사에서는 "A2A 자동 노출 / 스레드 · 런 API 내장" 을 이유로 `langgraph-api`
기반 런타임을 채택했었다. 그러나 실제 Docker 기동 검증 단계에서 다음이 드러났다:

1. 공식 이미지 `langchain/langgraph-api:*` 는 ENV 로
   `LANGGRAPH_RUNTIME_EDITION=postgres`, `LANGSMITH_LANGGRAPH_API_VARIANT=licensed`
   를 미리 박아둔다 → 기동 시 **LangGraph Cloud 라이센스 검증**
   (`LANGGRAPH_CLOUD_LICENSE_KEY`) 요구.
2. 체크포인트 영속성을 제공하는 `langgraph-storage-postgres` 는 PyPI 공개되지 않은
   상업 패키지이며 license 검증이 **코드에 박혀 있음** (환경변수로 우회 불가).
3. OSS `langgraph-runtime-inmem` 만 쓰면 영속성이 없어 "체크포인트 있어야 복구 가능"
   이라는 본래 목적 달성 불가.

정리하면: **OSS 경로로 "A2A + Postgres 체크포인트" 를 얻으려면 `langgraph-api`
를 통하지 않고 자체 FastAPI 에 `langgraph-checkpoint-postgres` 를 직접 wiring** 하는
것이 유일하게 깨끗한 답이었다. 자체 구현 비용은 A2A 라우트 ~200 줄 수준이고,
그 대가로 라이센스 종속 없이 완전한 제어와 OSS 영속성을 모두 얻는다.

잃은 것: langgraph-api 가 내장 제공하던 `/threads`, `/runs`, `/assistants` REST API,
LangGraph Studio 연동, SSE 스트리밍 기본 구현. 필요해지면 그때 자체 구현하거나
재평가.

---

## 참고 자료

- [A2A Protocol v1.0 Specification](https://a2a-protocol.org/latest/specification/)
- [LangGraph Checkpointing (PostgresSaver)](https://langchain-ai.github.io/langgraph/how-tos/persistence_postgres/)
- [a2a-samples: python/agents/langgraph](https://github.com/a2aproject/a2a-samples/tree/main/samples/python/agents/langgraph)
