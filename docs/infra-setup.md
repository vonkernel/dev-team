# 로컬 인프라 셋업 & GUI 도구 연결 가이드

로컬에서 dev-team 인프라(Neo4j + MongoDB + Valkey)를 띄우고, 각 데이터 시스템을 GUI 도구로 관찰하는 방법을 정리한다.

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
| `MONGO_INITDB_ROOT_USERNAME` | `root` | |
| `MONGO_INITDB_ROOT_PASSWORD` | `devteam_mongo` | |
| `MONGO_APP_DB` | `dev_team` | 앱 DB 이름 |
| `MONGO_PORT` | `27017` | |
| `VALKEY_PORT` | `6379` | |

### 기동

```bash
docker compose -f infra/docker-compose.yml --env-file .env up -d
```

### 상태 확인

```bash
docker compose -f infra/docker-compose.yml --env-file .env ps
```

3개 컨테이너가 `healthy` 로 표시되고, init one-shot 서비스 2개(`neo4j-init`, `mongo-init`)가 `Exited (0)` 이면 정상.

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

## 3. MongoDB Compass

MongoDB 공식 GUI. 각자 플랫폼에 맞게 **MongoDB Compass** 를 설치한다.

### 연결
`New connection` → Connection string 에 아래 입력:

```
mongodb://<MONGO_INITDB_ROOT_USERNAME>:<MONGO_INITDB_ROOT_PASSWORD>@localhost:27017/?authSource=admin
```

`.env` 기본값 기준이면:

```
mongodb://root:devteam_mongo@localhost:27017/?authSource=admin
```

> ⚠️ 실제 비밀번호가 포함된 connection string 을 공유하거나 저장하지 말 것. Compass 의 connection favorites 는 로컬에만 남겨둘 것.

### 기본 활용
- 좌측 databases 트리에서 `dev_team` 선택 (아직 쓰기가 없으면 표시되지 않을 수 있음 — 첫 쓰기 시점에 생성됨)
- Collection 을 클릭하면 문서 목록/인덱스/집계 등 확인 가능

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
docker logs dev-team-mongo-init
```
해결 후 재실행:
```bash
docker start -a dev-team-neo4j-init
docker start -a dev-team-mongo-init
```

### 포트가 이미 점유되어 바인딩 실패
`.env` 에서 해당 포트 변수를 다른 값으로 변경하고 재기동:
```bash
docker compose -f infra/docker-compose.yml --env-file .env down
# .env 에서 NEO4J_HTTP_PORT, MONGO_PORT, VALKEY_PORT 등 수정
docker compose -f infra/docker-compose.yml --env-file .env up -d
```

### 완전 초기화
```bash
docker compose -f infra/docker-compose.yml --env-file .env down -v
docker compose -f infra/docker-compose.yml --env-file .env up -d
```
