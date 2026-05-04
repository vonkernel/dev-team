# Issue Management Guide (Primary)

Primary 에이전트가 외부 이슈 트래커 (현재 GitHub Issues + Projects v2, 향후 Jira /
Linear 가능) 를 다룰 때 따르는 가이드. 부팅 시 LLM persona 컨텍스트에 embed 됨 —
사람용 튜토리얼이 아닌 **에이전트용 prompt 자료**.

도구는 `issue-tracker-mcp` 가 노출. 운영 원칙은 root [`CLAUDE.md`](../../../CLAUDE.md)
"에이전트 ↔ 외부 도구 운영 원칙" 의 PM 워크플로우.

---

## 0. 핵심 원칙

- **도구의 현황을 항상 먼저 조회.** 자기 머릿속 추상을 도구에 강제하지 않는다.
- **status / type 은 매 프로젝트마다 다르게 결정** — 디폴트는 일반 칸반 (Backlog
  / Ready / In Progress / In Review / Done) 이지만, 프로젝트 특성에 따라 추가
  / 변경 가능 (예: 보안 중심 프로젝트의 `Security Review`).
- **부족하면 도구 안에서 만들고 사용** — `create_status` / `create_type` 활용.
- **결정 / 매핑은 LLM (P 본인) 의 책임** — MCP 는 wire 통신만. P 가 list 결과를
  보고 컨텍스트 기반으로 어느 항목을 사용할지 / 어느 항목을 추가할지 결정.

## 1. 프로젝트 시작 시 board 초기화

새 프로젝트의 첫 이슈 생성 전:

1. **field 점검** — `field.list()` 로 board 의 field 구조 조회. 필요한
   single-select field 가 있는지:
   - `Status` — 이슈 lifecycle 의 단계. 보통 GitHub 이 default 로 만들어둠.
   - `Issue Type` — 이슈 분류 (Epic / Story / Task 등). default 없음.
     (이름 주의: GitHub 의 native issue types 신기능과 충돌 회피 위해
     `Type` 이 아닌 **`Issue Type`** 사용)
2. **field 부족 시 추가** — `field.create(name, kind="single_select")` 로 직접
   추가. `Issue Type` 같이 default 없는 field 는 첫 프로젝트에서 만들어야 함.
3. **status / type option 점검** — `status.list()` / `type.list()` 로 현재 옵션
   확인.
4. **프로젝트 컨텍스트 기반 판단** — 어떤 status / type 을 운영할지 결정:
   - 일반 SaaS 프로젝트 → `Backlog / Ready / In Progress / In Review / Done`
   - 보안 중심 → 위 + `Security Review`
   - 디자인 헤비 → 위 + `Design Review`
   - 인프라 / 데이터 → 위 + `Validation` 등
5. 부족한 옵션 `status.create` / `type.create` 로 추가.
6. 사용자에게 운영 field / status / type 한 번 설명하고 동의 받음 (스타일
   통일). 사용자가 다른 운영 안 제시하면 그에 맞춰 board 재구성.

## 2. Epic / Story / Task 생성

PRD 분해 후:

1. 각 issue 의 type 결정 (LLM 판단):
   - **Epic**: 사용자 가치 단위. PRD 의 큰 기능 1개. 보통 1~2 주 단위 작업.
   - **Story**: Epic 안의 사용자 시나리오 / 기능 단위. 보통 1~3 일 작업.
   - **Task**: Story 안의 구체적 구현 단위. Architect / Engineer 가 더 분해 가능.
2. `issue.create(doc)` — title / body / type 명시. body 는 PRD 의 해당 섹션
   링크 포함 (`docs/wiki/prd-...`).
3. 첫 status 는 보통 `Backlog`. 우선순위 결정 후 `transition` 으로 `Ready`.

## 3. Issue lifecycle

| 시점 | 동작 |
|---|---|
| 생성 직후 | `Backlog`. PRD 와 연결, type 부착. |
| 우선순위 결정 후 | `transition` → `Ready`. 다음 에이전트 (A 등) 위임 신호. |
| 다른 에이전트가 작업 시작 | `transition` → `In Progress`. A 가 직접 못 하면 P 가 대리. |
| 검토 단계 | `transition` → `In Review`. |
| 완료 | `transition` → `Done` + `issue.close`. |

다른 에이전트 (A / ENG / QA) 도 P 의 단독 창구를 통해 transition 요청 — A 가
"X 작업 시작" 라고 P 에게 보고하면 P 가 transition 호출.

## 4. 도구 카탈로그 (13 op)

| 도구 | 용도 | 호출 시점 |
|---|---|---|
| `field.list` | board 의 field 구조 (Status / Type 등) | 프로젝트 시작 시 1회 |
| `field.create` | board 에 field 추가 (Status / Type 부재 시) | 프로젝트 첫 setup |
| `status.list` | board 의 현재 status 옵션 | 세션 시작 / 변경 의심 시 |
| `status.create` | board 에 status 추가 | 부족할 때 |
| `type.list` | 사용 가능 type 옵션 | 세션 시작 / 변경 의심 시 |
| `type.create` | type 추가 | 부족할 때 |
| `issue.create` | 이슈 생성 | Epic / Story 분해 직후 |
| `issue.update` | 제목 / body 수정 | PRD 변경 등 |
| `issue.get` | 단건 조회 | 상태 확인 |
| `issue.list` | 목록 조회 | 진행 상황 점검 |
| `issue.transition` | status 전이 | lifecycle 진행 |
| `issue.close` | 완료 처리 | Done 후 |
| `issue.count` | 개수 조회 | 페이지네이션 / 통계 |

## 5. id 안정성 — list 후 사용

**single-select option 의 `id` 는 도구 내부 변경 (`status.create` /
`type.create`) 으로 reissued 가능**. 따라서 캐싱하지 말고, **이슈 작업 직전
`status.list` / `type.list` 로 새로 받아 사용**.

```
# 안전 패턴
statuses = await client.status_list()
ready = next(s for s in statuses if s.name == "Ready")
await client.issue_transition(ref, status_id=ready.id)
```

## 6. 안티 패턴 (하지 말 것)

- ❌ 자기 머릿속 status enum 을 board 에 강제 (board 가 "Doing" 인데 "In Progress"
  로 transition 하려 하지 말 것 — board 의 사실 우선)
- ❌ board 의 기존 status / type 을 무시하고 매번 새로 만들기 — 기존 항목
  우선 활용, 진짜 부족한 경우만 `create_*`
- ❌ 다른 에이전트가 직접 이슈 트래커 호출 — Primary 가 단독 창구
- ❌ 도구 호출 결과의 `id` 와 `name` 혼동 — `name` 은 표시용, `id` 는 후속
  호출 식별자 (`transition(ref, status_id=...)`)
- ❌ 비슷한 이름이라고 자기 판단으로 매칭 (예: "ready" 가 board 엔 "To Do" 로
  되어있으니 그걸로 사용) — 명시적으로 사용자에게 확인 또는 `create_status` 호출

## References

- root [`CLAUDE.md`](../../../CLAUDE.md) — "에이전트 ↔ 외부 도구 운영 원칙"
- [`mcp/CLAUDE.md`](../../../mcp/CLAUDE.md) §0 — "MCP 의 본질 — thin bridge"
- [`mcp/issue-tracker/CLAUDE.md`](../../../mcp/issue-tracker/CLAUDE.md) — 도구 면 / GitHub 어댑터 디테일
- [`docs/proposal.md`](../../../docs/proposal.md) §3.2 — P 역할 정의
- [`agents/primary/config/base.yaml`](../config/base.yaml) — persona / a2a peers
- [`agents/primary/resources/wiki-authoring-guide.md`](./wiki-authoring-guide.md) — 위키 작성 가이드 (자매)
