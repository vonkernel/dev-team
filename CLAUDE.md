# dev-team 프로젝트 작업 규칙 (Claude)

이 프로젝트에서 반복적으로 지적받은 사항의 영구 기록. 세션마다 되풀이되지
않도록 매 작업 전에 확인한다.

## 다이어그램

- **ASCII 도식 금지.** 모든 구조/흐름 도식은 **Mermaid** 사용
  (`flowchart`, `sequenceDiagram`, `block-beta` 등).
- 이미 존재하는 ASCII 도식을 발견하면 교체 대상.

## Git 워크플로우

- **커밋은 논리 단위로 분리.** 대규모 변경을 하나의 커밋에 몰아넣지 말고
  관심사별로 쪼갠다 (예: 의존성 편집 / 구현 / 문서 / 설정은 별개 커밋).
- **PR description 은 변경 내용 (요약 / 결정 / 후속 작업 등) 만 기술.** Commit 목록은 GitHub PR UI 에서 자동으로 보이므로 description 안에 별도 commit table / 목록을 만들지 않는다 — 갱신 부담만 늘고 정보 중복.
- **PR description 은 변경 내용이 추가될 때마다 갱신.** 초기 작성 후 방치하지 않는다.
- **PR 머지 직후 루틴:**
  1. 관련 이슈 body 에 **완료 요약** 추가 (원 스코프 대비 변경점 병기).
  2. 칸반: `In Review` → **Done**.
  3. 로컬 `main` 동기화 + 머지된 브랜치 삭제.

## 이슈 작성 및 상태 전이 워크플로우

- `gh issue create --body` 에 heredoc 을 쓰면 백틱이 이스케이프되어 렌더가
  깨진다. **항상 `--body-file <파일>` 로 별도 작성**.

- **칸반 상태는 작업 시점에 맞춰 즉시 전이한다. 건너뛰지 말 것:**

  | 전이 | 언제 |
  |---|---|
  | (생성) → **Todo** | 이슈 생성 직후 — 칸반 item-add 로 등록 필수 |
  | Todo → **In Progress** | **실제 브랜치 파고 코드 수정 시작하는 시점** (첫 커밋 전) |
  | In Progress → **In Review** | PR 생성 직후 |
  | In Review → **Done** | PR 머지 확인 직후 (자동 close 여부와 무관하게 수동으로 옮김) |

- **자주 실수하는 패턴 금지**:
  - Todo 에서 바로 In Review 로 점프 (In Progress 단계 생략) ❌
  - PR 머지 후 Done 처리 누락 (이슈만 closed, 칸반은 In Review 잔류) ❌
  - 이슈는 생성했는데 칸반에 item-add 안 함 ❌

- 실제 작업에 착수할 때 **맨 먼저** 이슈 상태를 In Progress 로 옮긴 뒤 구현.

## 설계 원칙 — SOLID 준수

코드 작성 / 리팩터링 시 항상 의식한다.

- **S**ingle Responsibility — 한 모듈 · 클래스 · 함수는 **하나의 변경 사유** 만
  가진다. 라우팅 / 프로토콜 번역 / I/O 어댑터 / 설정 / 미들웨어는 서로 다른 파일.
- **O**pen/Closed — 기존 코드 수정 없이 확장 가능해야 한다. 새 A2A 메서드 / 새
  에이전트 / 새 upstream backend 추가 시 **dispatcher 나 기존 클래스 본문을
  수정할 일이 없어야** 함 (registry / abstract base / 인스턴스 추가로 해결).
- **L**iskov Substitution — 추상 타입을 사용하는 코드는 그 모든 하위 타입에 대해
  정상 동작해야 한다. Protocol / ABC 로 계약 명시.
- **I**nterface Segregation — 크고 뭉뚱그린 인터페이스 대신 사용자 별 좁은 인터
  페이스. 클라이언트가 쓰지 않는 메서드에 의존하지 않도록.
- **D**ependency Inversion — 상위 모듈은 하위 구현 세부사항(httpx, 특정 DB
  드라이버 등) 에 직접 의존하지 않고 **추상(인터페이스 / Protocol)** 에 의존.
  구체 구현은 조립 레이어(`main.py` lifespan 등) 에서 주입.

### 실전 체크리스트

- 새 파일에 200 줄 넘는 함수 / 100 줄 넘는 핸들러가 생기고 있다면 **SRP 재검토**.
- `if method == "X": ...; elif method == "Y": ...` 식 분기가 늘어나면 **OCP
  재검토** — registry / 전략 패턴으로.
- 라우트 핸들러가 `httpx` / `psycopg` / 특정 SDK 를 직접 import 하고 있으면
  **DIP 위반** — 어댑터 클래스로 한 단계 감싸고 `request.app.state.<abstraction>`
  으로 접근.
- "그냥 지금만 필요해서 섞어 씀" → 나중에 두 번째 유사 사례가 생기면 **즉시
  추상화 분리** (YAGNI 와 균형: 단일 사용엔 추상화 금지, 2번째 등장 시 추상화).

## 모듈 코드 구조 (Python 패키지 공통)

새 Python 모듈 (에이전트 / MCP 서버 / shared 서브 모듈) 작성 시 다음 구조 따른다.

> 디렉터리별 추가 규약:
> - **MCP 서버**: [`mcp/CLAUDE.md`](mcp/CLAUDE.md) — thin bridge 원칙, API-client 패턴 등
> - **shared 서브패키지**: [`shared/CLAUDE.md`](shared/CLAUDE.md) — Pattern A (out-of-process service SDK) vs Pattern B (in-process infra library) 분류 가이드

- **책임별 디렉터리 분리**:
  - `schemas/` — Pydantic 모델만 (DTO / validation)
  - `repositories/` — 외부 자원 CRUD (DB / HTTP / file). ABC + concrete 한 쌍씩
  - `tools/` 또는 `handlers/` — 외부 노출 인터페이스 (MCP tool / FastAPI route 등)
  - 1 파일 1 책임. 200줄 넘으면 분리 신호.
- **Repository 패턴 (DIP / OCP)**:
  - `AbstractRepository[T]` ABC 가 generic CRUD 계약 (`upsert`, `get`, `list`, `delete`, `count`)
  - collection / entity 별 concrete 클래스. 새 entity = 새 파일 1개 (schemas/X + repositories/X + tools/X) + 등록 1줄. **기존 코드 무수정 (OCP)**
  - 외부 노출 함수 (tools/handlers) 는 repository 만 호출. 직접 driver (`asyncpg`, `httpx`) 호출 금지
- **DI via lifespan**:
  - 외부 자원 (DB pool, MCP client, LLM 등) 은 lifespan 에서 생성 → `app.state` 또는 의존성 주입으로 전달
  - 모듈 레벨 전역 변수 / 싱글턴 금지 (테스트성 ↓)
- **Schema validation**:
  - 입력 / 출력 모두 Pydantic 모델로 한 번씩 통과
  - DB row → Pydantic 직렬화는 repository 가 책임 (raw dict 가 외부로 새지 않게)
- **테스트 분리**:
  - Repository 단위 = `testcontainers` 로 실 인프라 (Postgres / Neo4j / Valkey)
  - Tool / handler 단위 = Repository mock (실 인프라 없이 빠르게)
  - 통합 = 컨테이너 기동 후 wire-level 호출 (HTTP / MCP)
- **AI 에이전트 런타임 자산**:
  - LLM 컨텍스트에 embed 되는 prompt 자료 (가이드 / 템플릿 / 예시) 는 `agents/{name}/resources/` 하위
  - 이미지 빌드 시 `COPY` 로 컨테이너에 포함. 수정 = 컨테이너 재배포 (자산 변경 = 행동 변경 추적)
  - 사람이 읽는 설계 문서는 `docs/`, AI 에이전트 운영 규약은 `CLAUDE.md`, **에이전트 자체의 prompt 자료는 `resources/`** — 셋 모두 다른 카테고리

## 통신 프로토콜 우선순위

내부 모듈 / 서비스 간 통신 시 어떤 프로토콜을 쓸지 합의. 새 통신 경로 추가 시 본 표에 매핑한 뒤 결정.

| 결 | 프로토콜 | 비고 |
|---|---|---|
| 에이전트 ↔ 에이전트 (대화) | **A2A** (`shared/a2a`) | Message / Task / FSM / contextId / traceId. JSON-RPC 2.0 위. |
| 에이전트·스크립트 ↔ 도구 / 데이터 서비스 | **MCP 우선** (REST 보다) | 도구 catalog / Pydantic 입출력 / 표준 에러 / traceId. streamable HTTP. |
| 외부 사용자 / 브라우저 ↔ Gateway | HTTP REST | 사용자 facing 표면 (UG `/chat` 등) |

### 결정 가이드

새 서비스 / 통신 경로가 생길 때:

1. **사용자 / 브라우저가 직접 부르는가?** → REST (Gateway 가 받아 내부에선 A2A / MCP 로 분기)
2. **상대가 LLM 에이전트 자기 자신인가?** → A2A (의도가 *대화*)
3. **상대가 도구 / 데이터 서비스인가? (LLM 이 호출할 수 있어야 하나?)** → **MCP** (REST 두 번 안 만든다)
4. **외부 SaaS 호출?** → 그쪽이 노출하는 프로토콜. 우리가 그 위에 MCP 어댑터로 감쌈 (예: GitHub API → IssueTracker MCP)

원칙: **REST 와 MCP 양쪽을 평행 노출 금지**. 도구 / 데이터 서비스는 MCP 한 채널. 사용자 facing 만 REST. LLM 이 아닌 클라이언트 (CHR 등) 도 MCP 사용 — 일관성 우선.

## 에이전트 ↔ 외부 도구 운영 원칙

에이전트가 외부 도구 (이슈 트래커 / 위키 / 등) 의 메타데이터 (status, issue
type, label, category 등) 를 다룰 때 따르는 원칙. **결정론적 프로그램이 아닌
LLM 에이전트** 의 특성에 기반.

### 데이터 접근 분담 (정정 — 2026-05, [docs/proposal/architecture-shared-memory.md](docs/proposal/architecture-shared-memory.md))

| 작업 | 호출자 | 호출 방식 |
|---|---|---|
| **자기 도메인 write** | 각 에이전트 (P / A / ENG / QA / CHR) | Doc Store / Atlas MCP **직접** |
| **단순 read** (자기 데이터 식별자 알 때) | 각 에이전트 | MCP 직접 |
| **정보 검색** (자연어 / 교차 쿼리) | 에이전트 → A2A → L | L 이 LLM ReAct 로 매핑 |
| **외부 리소스 조사** (라이브러리 docs / URL / web search) | 에이전트 → A2A → L | **L 단독 전담** ([docs/proposal/architecture-external-research.md](docs/proposal/architecture-external-research.md) 의 3 트랙) |
| **외부 도구 sync** (예: Doc Store ↔ GitHub) | 책임 에이전트 (P) | 외부 MCP 직접 |

CHR (Chronicler, #34) 의 직접 write 패턴이 다른 에이전트에도 일관 적용된
형태. write 시 LLM dispatch 비용 절감, traceability 향상, 사서 비유 (L = read
사서) 정확화.

### 도메인 추상은 LLM 런타임 결정 — 코드 enum 박지 않는다

- 에이전트의 status / type / category 같은 도메인 추상은 **매 프로젝트 / 작업
  컨텍스트마다 달라진다**. 보안 중심 프로젝트는 `Security Review` status 가
  필요할 수 있고, 디자인 헤비 프로젝트는 `Design Review` 가 필요할 수 있다.
- 따라서 에이전트 코드 안에 `IssueStatus(StrEnum)` / `IssueType(StrEnum)` 처럼
  결정론적 enum 으로 박지 않는다. **LLM 이 런타임에 컨텍스트를 보고 판단**.
- 정적 매핑 테이블 / 정규화 규칙을 어딘가에 박는 것도 같은 문제 — false
  abstraction.

### 외부 도구 메타데이터 운영은 에이전트 자율 (PM 워크플로우)

에이전트는 도구의 사용자(PM) 처럼 행동:

1. **현황 조회** — 도구가 가진 현재 메타데이터 목록 조회 (`list_*`).
2. **컨텍스트 기반 판단** — 프로젝트 / 작업 컨텍스트에 맞는 추상 결정 (LLM 추론).
3. **부족하면 도구 안에서 생성** — `create_*` 로 도구에 직접 추가.
4. **그 위에서 작업** — `transition` / `create(issue)` 등.

에이전트가 자기 추상을 외부 도구에 sync 하는 게 아니라, 도구의 현재 상태에
맞춰 자기 추상을 운영. 매 작업이 자기-완결적.

이 원칙은 에이전트 측 책임. 도구 어댑터 (MCP 서버) 측은 매핑 / 결정 로직 0
을 유지 — 자세한 건 [`mcp/CLAUDE.md`](mcp/CLAUDE.md) §0.

## 에이전트 명명 약어

| 에이전트 | 약어 | 도입 |
|---|---|---|
| Primary | **P** | M2 (구현됨) |
| User Gateway | **UG** | M2 (구현됨) |
| Librarian | **L** | M3 (#38) |
| Chronicler | **CHR** | M3 (#34) |
| Architect | **A** | M4 (#45) |
| Engineer | **ENG** | M5+ |
| QA | **QA** | M5+ |

### 사용 컨텍스트별 표기 규칙

| 컨텍스트 | 표기 |
|---|---|
| **이슈 / 커밋 메시지 / PR 제목·본문 / 채팅** | **약어 권장** — 짧고 가독성 우선 (예: `P / A 분담`, `Eng+QA 페어`) |
| **공식 문서 (`docs/proposal*.md` / sub doc / README)** | **정식 이름 사용** — Primary / Architect / Librarian / Engineer (단 QA 는 그대로). 첫 등장 시 약어 병기 가능 |
| **에이전트 persona text (`agents/*/config/base.yaml`)** | **정식 이름 사용** — LLM 컨텍스트에 임베드되므로 의미 전달 정확성 우선 |
| **코드 / 식별자 / 파일명** | 긴 이름 (`primary` / `chronicler` 등) 또는 약어 (`be` / `fe` 같은 specialty) — 기존 컨벤션 그대로 |

새 에이전트 추가 시 본 표에 등록.

## 포트 컨벤션

호스트 노출 포트의 의미적 대역. 새 컨테이너 추가 시 따른다.

| 대역 | 용도 |
|---|---|
| 5000~7999 | 인프라 (Postgres / Valkey / Neo4j 등) |
| 8000~8099 | 사용자 facing (UG 등) |
| 9000~9099 | **에이전트 컨테이너** (primary=9001, librarian=9002, architect=9003, ...) |
| 9100~9199 | **MCP 서버** (doc-store=9100, issue-tracker=9101, wiki=9102, atlas=9103, ...) |

새 에이전트 / MCP 추가 시 같은 대역 안에서 sequential 할당. 변경 시 본 표 즉시 갱신.

## 범위 / 지시 준수

- **시키지 않은 것은 하지 말 것.** 사용자의 지적을 과잉 해석해 스펙 밖 코드
  변경을 하지 않는다. 지적의 원래 맥락에 머문다.
- **"조사해" / "판단해"** → 근거 제시 + 추천 → 사용자 확인 후 실행.
- **"작업하지 말고"** → 이슈 생성 / 문서 정리까지만, 구현 보류.
- **한 번 결정된 범위는 임의로 확장하지 않는다.** 필요해 보이면 별도 이슈로 분리
  제안 후 사용자 승인 받는다.

## 검증 / 호들갑 금지

- **실제 입증 없이 "완벽히 작동"/"정상 동작"/"검증 완료" 주장 금지.**
  `curl`, 실제 호출, 로그 확인 등 **구체 근거** 먼저.
- **정직한 한계 표기.** 불확실한 부분은 "이 부분은 확인 안 됨" 으로 명시.
- **원인 분석 시 코드 grep 은 시작점이지 답변이 아니다.** 공식 문서 / 실제 런타임
  동작을 우선 확인.

## 조사 / 기술 선택

- **의존성 버전**: 사용 전에 PyPI / npm 최신 stable 확인 후 명시. 추측 금지.
- **기술 스택의 라이선스 / OSS 여부** 사용 전에 한 번 확인. 특히 베이스 이미지는
  proprietary 런타임이 박혀 있을 수 있음 (→ `langchain/langgraph-api` 사례).

## 파일 / 스키마 수정

- **사용자가 허가하지 않은 스키마 · 데이터 모델 결정 금지.** 특히 init 스크립트
  에서 임의로 컬렉션 / 인덱스 / 테이블을 만들지 않는다. 연결 · 권한 · DB 생성
  수준에 머무르고 스키마는 별도 이슈에서.
- **파일 생성 위치는 근거 기반.** 모호하면 사용자에게 선택지 제시.

## Docker / 로컬 환경

- **사용자가 검증 중인 compose 스택을 임의로 `down` 하지 않는다.** 검증
  진행 중일 가능성 고려.
- `.env`, `overrides/*.yaml` 같은 로컬 시크릿 파일은 **생성만 유도** 하고
  실제 값 입력은 사용자에게 맡김. 채팅에 노출된 키가 있으면 **로테이션 권고**.

## 문서화

- 주요 결정은 **코드 주석** + **별도 문서(`docs/` 또는 모듈별 README/docs)** 에
  근거와 함께 기록. "왜 이렇게 했는가" 가 누락되지 않게.
- 반복 지적된 규칙은 **본 CLAUDE.md 에 즉시 추가**. 동일 실수를 또 하지 않도록.
