# MCP 서버 — 공통 작업 규약

본 디렉터리 (`mcp/*`) 의 모든 MCP 서버가 따르는 골격. AI 에이전트 / 인간 모두
새 MCP 서버 작성 / 수정 시 본 문서 + root `CLAUDE.md` + `mcp/<name>/CLAUDE.md`
세 계층을 함께 따른다.

**Reference 구현**: `mcp/doc-store/` — 본 문서의 패턴이 처음 적용된 사례.
새 MCP 작성 시 디렉터리 구조 / 파일 명명을 그대로 본떠도 무방.

---

## 0. MCP 의 본질 — thin bridge

본 디렉터리의 모든 MCP 서버는 외부 도구 / 데이터 서비스에 대한 **얇은 다리**
다. 호출자(에이전트)와 실 도구 사이 wire-level 통신만 담당.

호출자 = LLM 에이전트. 에이전트의 도메인 추상은 매 프로젝트마다 달라진다
(root [`CLAUDE.md`](../CLAUDE.md) "에이전트 ↔ 외부 도구 운영 원칙"). MCP 가
중간에서 매핑 / 정규화를 박아두면 그 자체가 false abstraction → 호출자
(LLM) 의 결정권을 흐림.

### 가지면 안 되는 것

- **매핑 로직** — 호출자의 추상을 도구의 사실에 맞춰 자동 매칭 X (예: status
  name 정규화 / case-insensitive 매칭 / synonyms 처리).
- **정규화** — 도구가 부르는 그대로 노출. lowercase / underscore / 공백 trim 등
  안 한다. 호출자가 받은 사실을 호출자 책임으로 해석.
- **결정 / 정책** — "이 status 가 없으면 비슷한 거 골라 사용" 같은 판단 X.
  호출자가 결정하고 명시적 도구 호출 (`create_*`) 로 표현.

### 가져야 하는 것

- **도구 현황 노출** — `list_*` 류로 현재 상태 그대로 반환 (id + name 등).
- **도구 변경 도구** — `create_*` / `update_*` 로 호출자가 명시적으로 도구
  상태를 바꾸게.
- **Pydantic 검증** — wire 모델 → 도메인 Pydantic 1회 통과 (§1.3.1).

### 단, 도구의 사실을 도메인에 맞게 변환은 OK

외부 도구의 wire response (예: GitHub REST 응답) 를 본 모듈의 Pydantic 모델
로 변환하는 것은 매핑이 아니라 **타입 안전성**. 도구의 사실을 보존하면서
도메인 모델로 표현 (§2.2).

금지되는 매핑은 호출자의 추상 ↔ 도구 사실 사이의 의미적 매핑.

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
- **파라미터 / 반환을 Pydantic 모델로 직접 사용** (§1.3.1 참조)

```python
# tools/<entity>.py
from mcp.server.fastmcp import Context
from <name>_mcp.mcp_instance import AppContext, mcp
from <name>_mcp.schemas.<entity> import <Entity>Create, <Entity>Read

def _ctx(ctx: Context) -> AppContext:
    return ctx.request_context.lifespan_context  # type: ignore[return-value]

@mcp.tool(name="<entity>.upsert", description="...")
async def upsert(ctx: Context, doc: <Entity>Create) -> <Entity>Read:
    return await _ctx(ctx).<entity>.create(doc)
```

### 1.3.1. Pydantic 파라미터 / 반환 — 표준 (필수)

**도구 함수의 파라미터 / 반환은 Pydantic 모델 직접 사용.** FastMCP 가 경계에서 자동 검증 + JSON schema 생성. `model_validate` / `model_dump` 의 수동 호출 금지.

| 측면 | 권장 ✅ | 비권장 ❌ |
|---|---|---|
| 파라미터 | `doc: <Entity>Create` | `doc: dict[str, Any]` + 함수 안 `model_validate` |
| 반환 | `<Entity>Read` / `list[<Entity>Read>]` / `<Entity>Read \| None` | `dict[str, Any]` + `model_dump(mode="json")` |
| 검증 실패 | FastMCP 가 자동으로 ValidationError → MCP 표준 에러 매핑 | 함수 안 try/except 로 수동 변환 |
| 도구 schema (`list_tools()`) | 필드별 타입 / 제약 정밀 노출 — LLM 클라이언트가 의미 파악 | `object` 로 노출 — 불투명 |

#### `dict[str, Any]` 가 정당한 경우

오직 **명시적 free-form** 데이터:
- `metadata` JSONB 컬럼 (스키마리스가 의도)
- `external_refs` (어댑터별 임의 구조)
- `structured` (page_type 마다 다른 형태)

이 필드들은 *Pydantic 모델 안에서 `dict[str, Any]` 타입으로* 두지, 도구 파라미터 자체를 dict 로 두지 말 것.

#### Optional / Update 패턴

`Update` 모델은 모든 필드를 `Optional` 로 두고 `model_dump(exclude_unset=True)` 로 patch (repository 안에서 처리). 도구 시그니처에는 `Update` 모델 그대로:

```python
@mcp.tool(name="<entity>.update")
async def update(ctx: Context, id: str, patch: <Entity>Update) -> <Entity>Read | None:
    return await _ctx(ctx).<entity>.update(UUID(id), patch)
```

#### 예외 — 동적 query 파라미터

`list` 도구의 `where` filter 같은 자유로운 등호 매칭은 `dict[str, Any]` 가 자연스러움 (모든 컬럼이 매칭 대상). 다만 **함수 안에서 화이트리스트 / SQL injection 방어 필수** (repository 가 처리).

```python
@mcp.tool(name="<entity>.list")
async def list_(
    ctx: Context,
    where: dict[str, Any] | None = None,
    limit: int = 100,
    offset: int = 0,
    order_by: str = "created_at DESC",
) -> list[<Entity>Read]:
    flt = ListFilter(where=where, limit=limit, offset=offset, order_by=order_by)
    return await _ctx(ctx).<entity>.list(flt)
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

### 1.5. 표준 도구 면 — 6 op (create + update 분리)

CRUD-able entity 마다 동일한 6 op. **create / update 는 분리** (Pydantic 타입이 서로 달라 — Create 는 required 필드, Update 는 all-optional patch). 단순한 upsert 로 합치면 typed schema 가 모호해져 §1.3.1 의 정신과 맞지 않음.

| 도구 | 시그니처 (Pydantic 직접) |
|---|---|
| `<entity>.create` | `(doc: <Entity>Create) → <Entity>Read` |
| `<entity>.update` | `(id: str, patch: <Entity>Update, expected_version?: int) → <Entity>Read \| None` |
| `<entity>.get` | `(id: str) → <Entity>Read \| None` |
| `<entity>.list` | `(where?: dict, limit, offset, order_by) → list[<Entity>Read]` |
| `<entity>.delete` | `(id: str) → bool` |
| `<entity>.count` | `(where?: dict) → int` |

추가 query 가 필요하면 collection 별 특수 도구 (예: `wiki_page.get_by_slug`) — 항상 6 op 위에 누적.

**Immutable entity** (audit log 류 — 예: `chats`, `a2a_messages`, `a2a_task_status_updates`, `a2a_task_artifacts`) 는 `update` 미노출 → 5 op (create / get / list / delete / count).

`expected_version` 은 `version` 컬럼이 있는 entity 한정 (optimistic locking 필요한 경우).

---

## 2. Backend 변형

### 2.1. DB-backed (Doc Store / Atlas)

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
| 9100 | doc-store (#35) |
| 9101 | issue-tracker (#36, M3) |
| 9102 | wiki (#37, M3) |
| 9103 | atlas (M4) |
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

### compose 등록 (`docker-compose.yml` — repo 루트)

```yaml
<name>-mcp:
  profiles: ["mcp", "agents"]
  build:
    context: .
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
- [ ] **compose 등록** — `docker-compose.yml` (repo 루트)
- [ ] **컨테이너 build / 부팅 / streamable HTTP 호출 검증**
- [ ] **CI 파이프라인 (있을 때)** — pyproject 의존 캐시 / 테스트 실행

---

## 6. 절대 금지 사항 (모든 MCP 공통)

- **stdio transport 사용 금지** — 컨테이너 간 통신은 streamable HTTP 만
- **모듈 레벨 전역 자원** (DB pool / HTTP client) — lifespan + DI 만
- **Repository / Adapter 우회 직접 driver 호출** (예: tools 에서 asyncpg 직접) — DIP 위반
- **Schema validation 우회** — 모든 도구 입력 / 출력은 Pydantic 1회 통과
- **인증 / 보안 미적용 시 호스트 외부 노출** — 내부망 전용. 외부 노출 필요 시 별 reverse proxy + auth
- **`langgraph` DB 직접 접근** — Doc Store MCP 만 `dev_team` DB 의 owner. 다른 MCP 가 같은 DB 를 만지지 않음 (소유권 원칙)

---

## 7. 관련 문서

- 본 root: [`/CLAUDE.md`](../CLAUDE.md) — 프로젝트 일반 규약 (모듈 코드 구조 / 포트 컨벤션 / resources 패턴 등)
- Reference 구현: [`mcp/doc-store/`](./doc-store/) — 본 문서의 패턴 1호
- Module guide 예시: [`mcp/doc-store/CLAUDE.md`](./doc-store/CLAUDE.md)
- 디자인 보고서 (#35): `/tmp/m3-35-design-proposal.md` — 본 패턴 결정 과정
