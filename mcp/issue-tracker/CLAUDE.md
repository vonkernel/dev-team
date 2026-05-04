# IssueTracker MCP — AI 에이전트 작업 규칙

본 모듈을 수정하는 AI 에이전트가 따라야 할 규약. root [`CLAUDE.md`](../../CLAUDE.md)
+ [`mcp/CLAUDE.md`](../CLAUDE.md) 위에 본 모듈 한정 사항.

---

## 1. 본 모듈의 역할

외부 이슈 트래커 (현재 GitHub Issues + Projects v2) 의 thin bridge. 매핑 /
정규화 / 결정 로직 0 ([`mcp/CLAUDE.md`](../CLAUDE.md) §0). 호출자(LLM 에이전트)
가 raw id 들고 호출.

| 항목 | 값 |
|---|---|
| Transport | streamable HTTP (MCP spec 2025-06-18) |
| 호스트 포트 | **9101** |
| 컨테이너 포트 | 8000 (uvicorn) |
| Backend | GitHub Issues + Projects v2 (REST + GraphQL) — 본 PR 첫 구현 |
| 인증 | env `GITHUB_TOKEN` (fine-grained PAT, scope: `repo` + `project`) |

---

## 2. 도구 면 (11 op)

| 도구 | 시그니처 | 비고 |
|---|---|---|
| `issue.create` | `(doc: IssueCreate) → IssueRead` | Project board 자동 등록 |
| `issue.update` | `(ref, patch: IssueUpdate) → IssueRead \| None` | title / body / type_id |
| `issue.get` | `(ref) → IssueRead \| None` | |
| `issue.list` | `(where?, limit, offset, order_by) → list[IssueRead]` | repo 의 issue (PR 제외) |
| `issue.close` | `(ref) → bool` | state=closed |
| `issue.count` | `(where?) → int` | search API |
| `issue.transition` | `(ref, status_id: str) → None` | Project board 의 Status field 갱신 |
| `status.list` | `() → list[StatusRef]` | board 의 Status field options |
| `status.create` | `(name: str) → StatusRef` | options 추가 (이름 중복 시 기존) |
| `type.list` | `() → list[TypeRef]` | board 의 Type field options |
| `type.create` | `(name: str) → TypeRef` | options 추가 |

`StatusRef` / `TypeRef` 는 `{id, name}` — `id` 가 후속 호출 식별자.

---

## 3. 추상 + 구현 (mcp/CLAUDE.md §2.2)

```
src/issue_tracker_mcp/
├── adapters/
│   ├── base.py         # IssueTracker ABC (11 op)
│   ├── github.py       # GitHubIssueTrackerAdapter (REST + GraphQL)
│   └── _github_http.py # httpx + GraphQL 헬퍼
├── factory.py          # ISSUE_TRACKER_TYPE → 어댑터 선택 (OCP)
├── schemas/
│   ├── issue.py        # IssueCreate / IssueUpdate / IssueRead
│   └── refs.py         # StatusRef / TypeRef
└── tools/
    ├── issue.py        # 7 op
    ├── status.py       # 2 op
    └── type.py         # 2 op
```

**OCP 추가**: 새 backend (Jira / Linear) = `adapters/<name>.py` + `factory._REGISTRY` 1줄 + 사용자 컨펌. 기존 코드 수정 0줄.

---

## 4. GitHub Project board 전제 조건

본 어댑터는 다음을 **전제**:

1. 대상 Project v2 board 가 owner-level (user 또는 organization) 에 존재
2. board 에 single-select 필드 **`Status`** 와 **`Type`** 두 개 모두 존재

전제 위반 시 lifespan 에서 fail-fast (helpful 에러 메시지). board UI 또는 별
setup 으로 추가 후 재기동. 어댑터가 자동 생성하지 않는 이유 — board 의 권위
적 구조에 자동 변경 가하면 thin bridge 원칙 위반.

field 의 option (특정 status / type 값) 추가는 `*.create` 도구로 호출자(P)가
명시적 결정.

---

## 5. 환경변수

| 변수 | 기본 | 의미 |
|---|---|---|
| `ISSUE_TRACKER_TYPE` | `github` | factory 가 보는 backend 식별자 |
| `GITHUB_TOKEN` | (필수) | fine-grained PAT |
| `GITHUB_TARGET_OWNER` | (필수) | user / organization |
| `GITHUB_TARGET_REPO` | (필수) | repo name |
| `GITHUB_PROJECT_NUMBER` | (필수) | Project v2 number |
| `HTTP_PORT` | `8000` | streamable HTTP 컨테이너 내부 포트 |

---

## 6. 절대 금지 (본 모듈 한정)

mcp/CLAUDE.md §6 위에 추가:

- **호출자의 status / type 추상을 자동 매칭** — name 정규화 / synonyms 매칭 등 X
- **board option 자동 생성 (lazy)** — `create_status` / `create_type` 명시 호출만
  허용. transition 시 status_id 가 없는 option 이면 에러
- **GitHub SDK (PyGithub 등) 도입** — httpx 직접 + GraphQL 직접만. 의존성 최소화

---

## 7. 관련 문서

- [`/CLAUDE.md`](../../CLAUDE.md) — "에이전트 ↔ 외부 도구 운영 원칙"
- [`mcp/CLAUDE.md`](../CLAUDE.md) §0 / §2.2 — thin bridge / API-client 패턴
- [`agents/primary/resources/issue-management-guide.md`](../../agents/primary/resources/issue-management-guide.md) — P 의 사용 가이드
- 이슈: #36
