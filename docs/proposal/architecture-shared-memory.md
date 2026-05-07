# Shared Memory 아키텍처

> 본 문서는 [`proposal-main.md`](../proposal-main.md) §2.5 에서 분리. (#66)

Shared Memory(Doc Store + Atlas)는 **공유 MCP 서버**가 thin CRUD 계층으로 노출
하며, 각 에이전트가 **자기 도메인 데이터를 MCP 통해 직접 write** 한다.
**Librarian** 은 사서 — DB 정보 검색과 외부 리소스 조사를 자연어 요청으로
받아 도구 호출로 매핑한다 (Shared Memory 박스 외부의 별도 컴포넌트).

## 분담 모델 (정정 — 2026-05)

| 작업 | 호출자 | 호출 방식 |
|---|---|---|
| **자기 도메인 write** | 각 에이전트 (Primary / Architect / Engineer / QA / CHR) | Doc Store / Atlas MCP **직접** |
| **단순 read** (자기 데이터 식별자 알 때) | 각 에이전트 | MCP 직접 가능 |
| **정보 검색** (자연어 / 교차 쿼리) | 에이전트 → A2A → Librarian | Librarian 이 자연어 → 도구 매핑 (사서) |
| **외부 리소스 조사** (라이브러리 docs / URL 페이지 / 일반 web) | 에이전트 → A2A → Librarian | **Librarian 단독 전담** — 다른 에이전트는 외부 트랙 직접 호출 X |
| **외부 도구 sync** (예: Doc Store ↔ GitHub Issues / Wiki) | 책임 에이전트 (예: Primary) | 외부 MCP (IssueTracker / Wiki) 직접 |

이 분담은 **CHR (#34) 이미 정착시킨 직접 패턴**을 다른 에이전트에 일관 적용
한 결과 — write 시 LLM dispatch 비용 절감, traceability 향상, 사서 비유 정확화.

## Librarian 의 역할

| 역할 | 입력 | 처리 | 출력 |
|------|------|------|------|
| **DB 정보 검색** | 에이전트의 자연어 질의 | Atlas + Doc Store 교차 쿼리 (LLM ReAct) | 자연어로 정리된 답변 |
| **조합 쿼리** | "context X 의 대화 로그" 같은 multi-collection 쿼리 | 여러 도구 순차 호출 후 정리 | 통합 결과 |
| **외부 리소스 조사** | 라이브러리 docs / 사용자 URL 페이지 / 일반 web 조회 | 3 트랙 도구 ([architecture-external-research](architecture-external-research.md)) 호출 후 정리 | 조사 결과 자연어 응답 |
| **(M5+) 자연어 / 의미 기반 검색** | 페이지 / 이슈 본문 검색 | full-text / semantic | 매칭 결과 |

> **Librarian 은 write 도구를 노출하지 않는다.** 각 에이전트가 자기 도메인 데이터를
> 직접 MCP 로 write. **Diff 색인은 Engineer 자체 색인 (옵션 A)** 으로 `#63` 시점에
> 확정 — 호출자 (Engineer) 가 자기 변경 diff 분석 → Atlas / Doc Store MCP 직접 write.

> **외부 리소스 조사는 Librarian 전담**. 다른 에이전트는 context7 / web-fetch / web_search
> 트랙을 직접 호출하지 않고 Librarian 에게 자연어 위임. Librarian 은 [architecture-external-research](architecture-external-research.md)
> 의 3 트랙을 단독으로 다룬다.

> **대화 로그 수집은 Librarian의 역할이 아니다.** 별도의 경량 Consumer인 Chronicler가 Valkey Streams 브로커를 통해 수집·저장한다. ([architecture-event-pipeline](architecture-event-pipeline.md) 참조)

## 접근 경로

| 경로 | 방식 | 용도 |
|------|------|------|
| **자기 도메인 write** | 에이전트 → MCP → DB | 직접 — wiki_pages / issues / atlas 등 |
| **정보 검색** | 에이전트 → A2A → Librarian → MCP → DB | 자연어 질의, 교차 참조 |
| **외부 리소스 조사** | 에이전트 → A2A → Librarian → 3 트랙 ([architecture-external-research](architecture-external-research.md)) | 라이브러리 docs / URL / web search |
| **Task Context 조립** | Engineer/QA → A2A → Librarian → Atlas | Code Agent 호출 전 필요한 파일/참조 시그니처 |
| **대화 로그 기록** | 에이전트 → Valkey Streams → Chronicler → MCP → Doc Store | A2A 대화 이력 수집 (Librarian 경유 X) |
| **외부 도구 sync** | 에이전트 → 외부 MCP (IssueTracker/Wiki 등) | Doc Store 의 데이터를 외부에 push |

## Diff 기반 색인 워크플로우

> **Engineer 자체 색인 (옵션 A) — `#63` 시점에 확정** (정정: 2026-05).
> Engineer 이 자기 변경 diff 를 분석해 Atlas / Doc Store MCP 에 직접 write.
> Diff → Atlas 매핑 자체는 LLM 추론으로 수행. 다른 에이전트 (Architect / Pairs / QA)
> 도 동일하게 자기 산출물을 직접 영속.
>
> 자세한 흐름은 [architecture-code-agent §Context Assembly](architecture-code-agent.md#context-assembly-흐름) 의 sequence diagram 참조 —
> Engineer Agent 가 diff 채택 후 변경된 OO 구조를 추출해 Atlas MCP 에 직접 update 한다.

## 접근 권한 매트릭스 (정정 — 2026-05)

| 주체 | MCP 직접 read | MCP 직접 write | A2A → Librarian (정보 검색 / 외부 조사) | Broker publish |
|------|:------------:|:------------:|:---------------:|:--------------:|
| **Librarian** | O | X — write 도구 미노출 (옵션 A 확정 — `#63`) | — | X |
| **Chronicler** | — | O (Doc DB, 대화 영속) | — | X (구독만) |
| **Primary** | O (자기 도메인 — wiki_pages / issues) | **O** (wiki_pages / issues + 외부 sync) | 정보 검색 + 외부 조사 | O |
| **Architect** (M4+) | O (atlas / wiki_pages) | **O** (atlas / wiki_pages — ADR 등) | 정보 검색 + 외부 조사 | O |
| **Engineer:{역할}** (M5+) | O (atlas / wiki_pages) | **O** (atlas — 코드 변경 색인) | 정보 검색 + 외부 조사 | O |
| **QA:{역할}** (M5+) | O | **O** (테스트 결과 / wiki_pages) | 정보 검색 + 외부 조사 | O |

**정정된 원칙:**
- **write = 각 에이전트 직접** — 자기 도메인 데이터를 MCP 통해 직접 영속.
  자기 데이터의 schema 는 자기가 가장 잘 앎.
- **정보 검색 = Librarian 통과** — DB 안에서 데이터를 찾아오는 것이 사서 역할.
  자기 데이터의 단순 read 는 직접도 가능하지만, 자연어 / 교차 쿼리는 Librarian 의 사서 역할 활용.
- **외부 리소스 조사 = Librarian 전담** — 라이브러리 docs / 사용자 URL / 일반 web search 모두 Librarian 단독 ([architecture-external-research](architecture-external-research.md)).
- **CHR 의 직접 패턴이 reference** — 결정론적 worker 도, LLM 에이전트도 일관.

**설계 원칙:**
- MCP 서버는 비즈니스 로직 없는 thin CRUD (mcp/CLAUDE.md §0)
- Librarian = 사서 (정보 검색 + 외부 리소스 조사) — LLM ReAct 매핑
- 에이전트 직접 write — schema 는 prompt 에 노출 (claude-sonnet-4-6 의 200K
  context 에서 미미한 부담)
- 외부 도구 sync (Doc Store ↔ GitHub 등) 는 책임 에이전트 (Primary) 가 외부 MCP 직접 호출
