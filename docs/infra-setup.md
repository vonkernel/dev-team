# 로컬 인프라 셋업 & GUI 도구 연결 가이드

로컬에서 dev-team 인프라(Neo4j + PostgreSQL + Valkey)를 띄우고, 각 데이터 시스템을 GUI 도구로 관찰하는 방법을 정리한다.

> **참고** — Doc Store 는 기존 MongoDB 에서 PostgreSQL + JSONB 로 전환되었다.
> 전환 배경은 [`docs/proposal/tech-stack.md`](./proposal/tech-stack.md) 의 §6.4 추상화 레이어 항목 및 이슈 #20 참조.

---

## 1. Quickstart

### 사전 준비
- Docker (Desktop 또는 Engine) 설치·기동
- 이 레포 clone

### 환경 변수 준비
루트에서 템플릿을 복사하고 필요 시 값만 수정한다.

```bash
cp .env.example .env
```

`.env` 의 기본값:

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `NEO4J_USER` | `neo4j` | Neo4j Community 는 변경 불가 |
| `NEO4J_PASSWORD` | `devteam_neo4j` | 8자 이상 |
| `NEO4J_HTTP_PORT` | `7474` | Neo4j Browser |
| `NEO4J_BOLT_PORT` | `7687` | Bolt (driver/GUI) |
| `POSTGRES_USER` | `devteam` | 단일 role, 양 DB 에 동일 적용 |
| `POSTGRES_PASSWORD` | `devteam_postgres` | |
| `POSTGRES_DB` | `langgraph` | langgraph-api 전용 DB (컨테이너 부팅 시 자동 생성) |
| `APP_DB` | `dev_team` | 애플리케이션 document DB (postgres-init 에서 추가 생성) |
| `POSTGRES_PORT` | `5432` | |
| `VALKEY_PORT` | `6379` | |

### 기동

```bash
docker compose -f infra/docker-compose.yml --env-file .env up -d
```

### 상태 확인

```bash
docker compose -f infra/docker-compose.yml --env-file .env ps
```

3개 컨테이너(`neo4j`, `postgres`, `valkey`)가 `healthy` 로 표시되고, init one-shot 서비스 2개(`neo4j-init`, `postgres-init`)가 `Exited (0)` 이면 정상.

### 중지 / 정리

```bash
# 컨테이너만 제거 (볼륨 = 데이터 유지)
docker compose -f infra/docker-compose.yml --env-file .env down

# 컨테이너 + 볼륨 모두 제거 (완전 초기화)
docker compose -f infra/docker-compose.yml --env-file .env down -v
```

---

## 2. Neo4j Browser (내장)

별도 설치 불필요. Neo4j 컨테이너가 내장 Web UI 를 제공한다.

### 접속
브라우저에서 http://localhost:7474

### 로그인
- Connect URL: `neo4j://localhost:7687`
- Authentication type: `Username / Password`
- Username: `.env` 의 `NEO4J_USER`
- Password: `.env` 의 `NEO4J_PASSWORD`

### 기본 활용
- 상단 커맨드 바에 Cypher 쿼리 입력
- 시작 예시:
  ```cypher
  SHOW CONSTRAINTS;
  SHOW INDEXES;
  MATCH (n) RETURN n LIMIT 25;
  ```

---

## 3. PostgreSQL GUI (DBeaver 권장)

**DBeaver Community** 설치를 권장한다 (오픈소스, 크로스플랫폼, Postgres/Neo4j/Valkey 를 단일 툴로 연결 가능). 단일 Postgres 전용이 더 편하다면 **pgAdmin 4** 를 써도 된다.

### 연결

DBeaver 의 `New Database Connection` → `PostgreSQL` 선택 후:

| 필드 | 값 |
|------|-----|
| Host | `localhost` |
| Port | `.env` 의 `POSTGRES_PORT` (기본 `5432`) |
| Database | `langgraph` 또는 `dev_team` (둘 다 각각 연결 프로파일로 저장 권장) |
| Username | `.env` 의 `POSTGRES_USER` (기본 `devteam`) |
| Password | `.env` 의 `POSTGRES_PASSWORD` |

> ⚠️ 실제 비밀번호가 포함된 connection 정보를 공유하거나 저장하지 말 것. DBeaver 의 saved connections 는 로컬에만 남겨둘 것.

### 두 DB 의 역할

| DB | 소유자 | 확인 대상 |
|---|---|---|
| `langgraph` | langgraph-api 프레임워크 | 체크포인트/스레드/런 테이블 (프레임워크가 직접 생성·관리) |
| `dev_team` | 애플리케이션 | PRD, Session/Task/Item, 대화 이벤트 로그 등 (JSONB 컬럼 적극 활용 예정) |

### 기본 활용

- 좌측 DB 트리에서 대상 DB 를 펼치면 `Schemas → public → Tables` 하위에 테이블 목록 확인
- JSONB 컬럼은 DBeaver 에서 자동으로 트리 형태 렌더링 (MongoDB Compass 의 nested view 와 유사)
- 쿼리 예시:
  ```sql
  -- langgraph DB
  SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';

  -- dev_team DB (JSONB 예시)
  -- SELECT id, payload -> 'title' AS title FROM prd LIMIT 5;
  ```

---

## 4. ARDM (Another Redis Desktop Manager) — Valkey 관찰용

**ARDM** 을 설치한다. Redis·Valkey 호환 GUI.

### 연결
`New Connection` → 항목 입력:

| 필드 | 값 |
|------|-----|
| Name | `dev-team-valkey` (자유) |
| Host | `127.0.0.1` |
| Port | `.env` 의 `VALKEY_PORT` (기본 `6379`) |
| Auth | 비워둠 (현재 로컬 dev 설정은 인증 없음) |

### 기본 활용 — 키 탐색
좌측 트리에서 DB 선택 → 키가 있으면 타입별로 표시.

### Stream 관찰 (`a2a-events`)

Chronicler 가 활성화되면 `a2a-events` 스트림에 이벤트가 쌓인다. ARDM 에서 확인하는 방법:

- 좌측 트리에서 `a2a-events` (type: `stream`) 선택
- 우측 패널에서 기록(entries) 목록 확인 — `id`, `field`, `value` 쌍 표시

### Stream 관련 기본 명령 (검증·실험용)

GUI 하단 CLI 또는 터미널에서 직접 확인하려면:

```bash
# 접속 (컨테이너 내부 CLI)
docker exec -it dev-team-valkey valkey-cli

# 예시
PING
XLEN a2a-events
XRANGE a2a-events - +
XINFO STREAM a2a-events
XINFO GROUPS a2a-events
XPENDING a2a-events chronicler-cg
```

Consumer group 은 Chronicler 가 기동하면서 생성하는 설계이므로, 현재(Chronicler 미구현) 단계에서는 group 이 없을 수 있다.

---

## 5. 문제 해결

### 컨테이너가 `unhealthy` 로 잡힐 때
```bash
docker compose -f infra/docker-compose.yml --env-file .env logs <service>
```

### init 컨테이너가 실패(exit code ≠ 0)로 끝날 때
```bash
docker logs dev-team-neo4j-init
docker logs dev-team-postgres-init
```
해결 후 재실행:
```bash
docker start -a dev-team-neo4j-init
docker start -a dev-team-postgres-init
```

### 포트가 이미 점유되어 바인딩 실패
`.env` 에서 해당 포트 변수를 다른 값으로 변경하고 재기동:
```bash
docker compose -f infra/docker-compose.yml --env-file .env down
# .env 에서 NEO4J_HTTP_PORT, POSTGRES_PORT, VALKEY_PORT 등 수정
docker compose -f infra/docker-compose.yml --env-file .env up -d
```

### 완전 초기화
```bash
docker compose -f infra/docker-compose.yml --env-file .env down -v
docker compose -f infra/docker-compose.yml --env-file .env up -d
```
