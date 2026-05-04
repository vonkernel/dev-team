# MCP 서버 — 공통 작업 규약

본 디렉터리 (`mcp/*`) 의 모든 MCP 서버가 따르는 골격. AI 에이전트 / 인간 모두
새 MCP 서버 작성 / 수정 시 본 문서 + root `CLAUDE.md` + `mcp/<name>/CLAUDE.md`
세 계층을 함께 따른다.

**Reference 구현**: `mcp/document-db/` — 본 문서의 패턴이 처음 적용된 사례.
새 MCP 작성 시 디렉터리 구조 / 파일 명명을 그대로 본떠도 무방.

---

## 1. 모든 MCP 공통 골격 (고정)

### 1.1. 디렉터리 구조

```
mcp/<name>/
├── CLAUDE.md                          # 본 모듈 한정 작업 규약
├── pyproject.toml                     # 의존 + dev extras
├── Dockerfile                         # python:3.13-slim 기반
├── src/<name>_mcp/
│   ├── __init__.py
│   ├── mcp_instance.py                # FastMCP 싱글턴 + lifespan + AppContext
│   ├── server.py                      # entry point (얇음)
│   ├── config.py                      # pydantic-settings env 로딩
│   ├── schemas/                       # Pydantic Create / Update / Read
│   │   ├── __init__.py
│   │   └── <entity>.py
│   ├── tools/                         # MCP 도구
│   │   ├── __init__.py                # side-effect import
│   │   └── <entity>.py                # module-level @mcp.tool()
│   └── [repositories/ 또는 adapters/]  # backend 따라 (§2 참조)
└── tests/
    ├── __init__.py
    ├── test_schemas.py
    └── test_<repos|adapters>.py
```

### 1.2. FastMCP 인스턴스 (`mcp_instance.py`)

- `FastMCP(name=, lifespan=, host="0.0.0.0", port=, transport_security=...)` 모듈 레벨 싱글턴
- `lifespan` 이 **`AppContext` dataclass yield** (이름 통일)
- AppContext 는 collection / adapter 별 instance 묶음 (frozen dataclass)
- 도구는 `ctx.request_context.lifespan_context.<X>` 로 접근

```python
@dataclass(frozen=True)
class AppContext:
    foo: FooRepository  # 또는 FooAdapter
    bar: BarRepository

@asynccontextmanager
async def _app_lifespan(_server: FastMCP) -> AsyncIterator[AppContext]:
    settings = Settings()
    # ...자원 생성...
    yield AppContext(foo=..., bar=...)

mcp = FastMCP(
    "<name>",
    lifespan=_app_lifespan,
    host="0.0.0.0",
    port=settings.http_port,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)
```

### 1.3. 도구 등록 패턴 (`tools/`)

- **module-level `@mcp.tool()` 데코레이터** — 함수가 `ctx: Context` 를 첫 인자로 받음
- `tools/__init__.py` 가 모든 collection 모듈을 side-effect import → 등록 트리거

```python
# tools/<entity>.py
from mcp.server.fastmcp import Context
from <name>_mcp.mcp_instance import AppContext, mcp

def _ctx(ctx: Context) -> AppContext:
    return ctx.request_context.lifespan_context  # type: ignore[return-value]

@mcp.tool(name="<entity>.upsert", description="...")
async def upsert(ctx: Context, doc: dict[str, Any]) -> dict[str, Any]:
    repo = _ctx(ctx).<entity>
    return (await repo.create(<Entity>Create.model_validate(doc))).model_dump(mode="json")
```

```python
# tools/__init__.py
from <name>_mcp.tools import (  # noqa: F401  side-effect imports
    entity_a,
    entity_b,
)
```

### 1.4. Entry point (`server.py`)

얇음. 도구 등록 trigger + `mcp.run("streamable-http")`.

```python
from <name>_mcp import tools as _tools  # noqa: F401  registers tools
from <name>_mcp.mcp_instance import mcp

def main() -> None:
    mcp.run(transport="streamable-http")

if __name__ == "__main__":
    main()
```

### 1.5. 5 op 표준 도구 면

CRUD-able entity 마다 동일한 5 op:

| 도구 | 시그니처 |
|---|---|
| `<entity>.upsert` | `(doc, id?, expected_version?) → dict` |
| `<entity>.get` | `(id) → dict \| null` |
| `<entity>.list` | `(where?, limit, offset, order_by) → list[dict]` |
| `<entity>.delete` | `(id) → bool` |
| `<entity>.count` | `(where?) → int` |

추가 query 가 필요하면 collection 별 특수 도구 (예: `wiki_page.get_by_slug`) — 항상 5 op 위에 누적.

Immutable entity (audit log 류) 는 update / upsert 미노출.

---

## 2. Backend 변형

### 2.1. DB-backed (Document DB / Graph DB)

```
src/<name>_mcp/
├── repositories/
│   ├── base.py                # AbstractRepository[CreateT, UpdateT, ReadT] ABC
│   ├── <entity>.py            # concrete (asyncpg 직접 사용)
│   └── __init__.py
├── db.py                      # pool lifespan + migration runner
└── ... (위 §1)

migrations/                    # yoyo-migrations 패턴
├── 001_<name>.sql             # forward
└── 001_<name>.rollback.sql    # rollback (별 파일)
```

- **driver**: asyncpg (Postgres) / neo4j (Neo4j). ORM 도입 금지
- **Migration**: yoyo, MCP 부팅 시 자동 적용 (`db.apply_migrations` in lifespan)
- **Optimistic locking**: `version` 컬럼 + `update_with_version(expected_version=)` 메서드
- **JSONB / 복합 타입**: repository 가 직렬화 책임 (`_to_jsonb` helper)

### 2.2. API-client (IssueTracker / Wiki / 외부 SaaS)

```
src/<name>_mcp/
├── adapters/
│   ├── base.py                # IssueTracker / Wiki ABC (interface 계약)
│   ├── github.py              # 구현체별 어댑터
│   ├── jira.py                # (M5+) 추가 어댑터
│   └── __init__.py
├── factory.py                 # config 의 type 필드로 구현체 선택 (OCP)
└── ... (위 §1)
```

- **driver**: httpx (REST) / 라이브러리별 SDK
- **Migration 없음** (외부 시스템 스키마 따라감)
- **Factory 패턴**: 새 구현체 추가 = `adapters/<name>.py` 작성 + factory 에 1줄 등록 (OCP)
- **Schema validation**: 외부 응답을 본 모듈의 Pydantic 모델로 변환 — wire 모델이 도메인으로 새지 않게

---

## 3. Transport / 운영

| 항목 | 값 |
|---|---|
| Transport | **streamable HTTP only** (stdio 사용 X — 컨테이너 토폴로지) |
| Host binding | `0.0.0.0` (컨테이너 내부, 노출 제어는 compose port mapping) |
| DNS rebinding 보호 | **off** (`TransportSecuritySettings(enable_dns_rebinding_protection=False)`) — 내부망 전용 |
| 포트 대역 | **9100~9199** (root CLAUDE.md "포트 컨벤션") |
| Endpoint path | `/mcp` (FastMCP default) |

### 포트 할당 표 (현재까지)

| 포트 | MCP |
|---|---|
| 9100 | document-db (#35) |
| 9101 | issue-tracker (#36, M3) |
| 9102 | wiki (#37, M3) |
| 9103 | graph-db (M4) |
| 9104+ | 향후 |

새 MCP 추가 시 본 표 즉시 갱신.

---

## 4. Container 패턴

```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY mcp/<name> /app/<name>
RUN pip install -e /app/<name>

WORKDIR /app/<name>
EXPOSE 8000

CMD ["python", "-m", "<name>_mcp.server"]
```

### compose 등록 (`infra/docker-compose.yml`)

```yaml
<name>-mcp:
  profiles: ["mcp", "agents"]
  build:
    context: ..
    dockerfile: mcp/<name>/Dockerfile
  image: dev-team/<name>-mcp:latest
  container_name: dev-team-<name>-mcp
  restart: unless-stopped
  environment:
    # 본 MCP 가 필요로 하는 env (DSN / API token / 등)
  ports:
    - "<host_port>:8000"
  depends_on:
    # Postgres / Valkey / Neo4j 등 backend 의존
```

`profiles: ["mcp", "agents"]` — `--profile mcp` 만 띄울 수 있고, 에이전트 함께 띄울 때도 (`agents`) 같이 올라옴.

---

## 5. 새 MCP 추가 절차 (체크리스트)

본 디렉터리에 새 MCP 추가 시:

- [ ] **이슈 + 컨펌** — 명세 + 추상화 레이어 / 도구 면 / 배포 형태 합의
- [ ] **포트 할당** — root CLAUDE.md "포트 컨벤션" + 본 문서 §3 표 갱신
- [ ] **`mcp/<name>/` 디렉터리 생성** — §1.1 구조 따라
- [ ] **`mcp/<name>/CLAUDE.md`** — 본 MCP 한정 규약 (collection 목록 / backend 디테일 / 새 entity 추가 절차 등)
- [ ] **pyproject.toml + Dockerfile** — §4 패턴 따라
- [ ] **`mcp_instance.py`** — FastMCP + lifespan + AppContext
- [ ] **`schemas/` + `[repositories|adapters]/` + `tools/`** — §1 / §2 패턴
- [ ] **`server.py`** — 얇은 entry point
- [ ] **테스트** — schemas 단위 + repository / adapter 통합
- [ ] **compose 등록** — `infra/docker-compose.yml`
- [ ] **컨테이너 build / 부팅 / streamable HTTP 호출 검증**
- [ ] **CI 파이프라인 (있을 때)** — pyproject 의존 캐시 / 테스트 실행

---

## 6. 절대 금지 사항 (모든 MCP 공통)

- **stdio transport 사용 금지** — 컨테이너 간 통신은 streamable HTTP 만
- **모듈 레벨 전역 자원** (DB pool / HTTP client) — lifespan + DI 만
- **Repository / Adapter 우회 직접 driver 호출** (예: tools 에서 asyncpg 직접) — DIP 위반
- **Schema validation 우회** — 모든 도구 입력 / 출력은 Pydantic 1회 통과
- **인증 / 보안 미적용 시 호스트 외부 노출** — 내부망 전용. 외부 노출 필요 시 별 reverse proxy + auth
- **`langgraph` DB 직접 접근** — Document DB MCP 만 `dev_team` DB 의 owner. 다른 MCP 가 같은 DB 를 만지지 않음 (소유권 원칙)

---

## 7. 관련 문서

- 본 root: [`/CLAUDE.md`](../CLAUDE.md) — 프로젝트 일반 규약 (모듈 코드 구조 / 포트 컨벤션 / resources 패턴 등)
- Reference 구현: [`mcp/document-db/`](./document-db/) — 본 문서의 패턴 1호
- Module guide 예시: [`mcp/document-db/CLAUDE.md`](./document-db/CLAUDE.md)
- 디자인 보고서 (#35): `/tmp/m3-35-design-proposal.md` — 본 패턴 결정 과정
