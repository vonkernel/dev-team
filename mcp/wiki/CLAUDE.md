# Wiki MCP — AI 에이전트 작업 규칙

본 모듈을 수정하는 AI 에이전트가 따라야 할 규약. root [`CLAUDE.md`](../../CLAUDE.md)
+ [`mcp/CLAUDE.md`](../CLAUDE.md) 위에 본 모듈 한정 사항.

---

## 1. 본 모듈의 역할

외부 wiki backend (현재 GitHub Wiki) 의 thin bridge. 매핑 / 정규화 / 결정 로직
0 (mcp/CLAUDE.md §0). 호출자 = P (proposal §6.1단계 — P 가 PRD 작성 후
doc-store + GitHub Wiki 양쪽 동기화).

| 항목 | 값 |
|---|---|
| Transport | streamable HTTP (MCP spec 2025-06-18) |
| 호스트 포트 | **9102** |
| 컨테이너 포트 | 8000 (uvicorn) |
| Backend | GitHub Wiki — 별 git repo (`<owner>/<repo>.wiki.git`) |
| Backend 호출 | subprocess git (Dockerfile 에 `apt install git`) |
| 인증 | env `GITHUB_TOKEN` (PAT, `repo` scope 가 wiki 권한 포함) |

---

## 2. 도구 면 (6 op)

| 도구 | 시그니처 | 비고 |
|---|---|---|
| `page.create` | `(doc: PageCreate) → PageRead` | slug 중복 시 RuntimeError (호출자가 update 하라는 신호) |
| `page.update` | `(slug, patch: PageUpdate) → PageRead \| None` | title / content / page_type / structured 부분 갱신 |
| `page.get` | `(slug) → PageRead \| None` | front matter parse |
| `page.list` | `() → list[PageRef]` | slug + title 만 (가벼움, 본문 미포함) |
| `page.delete` | `(slug) → bool` | 페이지 영구 삭제 (rm + commit + push) |
| `page.count` | `() → int` | 페이지 개수 |

`page` 는 wiki 의 자료. `transition` / `close` 같은 lifecycle 없음 — just data.

---

## 3. 추상 + 구현 (mcp/CLAUDE.md §2.2 + ISP)

```
src/wiki_mcp/
├── adapters/
│   ├── base.py            # PageOps + Wiki (composition) ABC
│   └── github/            # 패키지 — 도메인별 모듈
│       ├── __init__.py    # GitHubWikiAdapter export
│       ├── adapter.py     # GitHubWikiAdapter (composition)
│       ├── page.py        # GitHubPageOps (subprocess git)
│       ├── _ctx.py        # 공유 _Ctx (owner / repo / token)
│       ├── _git.py        # asyncio.create_subprocess_exec wrapper
│       └── _front_matter.py  # YAML front matter encode / decode
├── factory.py             # WIKI_TYPE → 어댑터 (OCP)
├── tools/page.py          # 6 도구 (delegate to wiki.pages.X)
├── mcp_instance.py        # FastMCP + lifespan + AppContext
└── server.py              # entry point
```

**OCP**: 새 backend (Notion / Confluence) = `adapters/<name>/` 패키지 + `factory._REGISTRY` 1줄.

---

## 4. front matter 컨벤션

페이지 파일 (`<slug>.md`) 의 첫 부분에 YAML metadata 인코딩:

```markdown
---
title: GuestBook PRD
created_at: 2026-05-04T17:39:00Z
updated_at: 2026-05-04T17:39:00Z
page_type: prd
structured:
  milestones: [{name: M1}]
---

# 본문...
```

표준 필드 (`title`, `created_at`, `updated_at`) + 도메인 필드 (`page_type`,
`structured`). doc-store `wiki_pages` schema 와 키 일치.

---

## 5. workdir lifecycle (token 보안)

GitHub Wiki = git repo. clone URL 에 token 임베드 (`https://x-access-token:{token}@github.com/...`).

**매 호출마다 임시 디렉터리 + 작업 후 `shutil.rmtree`** — `.git/config` 의 token
leak 방지.

trade-off: 매 호출 clone 비용. M3 단계 wiki 작은 규모 (~10 페이지) 에선 OK.
대규모 (>100 페이지 + 잦은 호출) 가 되면 lifespan 내 단일 working clone +
pull/push 패턴으로 후속 최적화.

---

## 6. 환경변수

| 변수 | 기본 | 의미 |
|---|---|---|
| `WIKI_TYPE` | `github` | factory backend 식별자 |
| `GITHUB_TOKEN` | (필수) | PAT, scope: `repo` (wiki 권한 포함) |
| `GITHUB_TARGET_OWNER` | (필수) | user / organization |
| `GITHUB_TARGET_REPO` | (필수) | repo name (`.wiki.git` suffix 자동) |
| `HTTP_PORT` | `8000` | streamable HTTP 컨테이너 내부 포트 |

---

## 7. 절대 금지

mcp/CLAUDE.md §6 위에 추가:

- **외부 wiki page 의 사람 직접 편집 가정** — 단방향 sync (P → wiki) 라 사람
  편집은 다음 sync 에 overwrite. P guide 에 명시.
- **subprocess `shell=True`** — args 는 list 로 전달 (injection 회피)
- **token 노출 (logging / 에러 메시지)** — git stderr 에 URL 포함될 수 있어
  로깅 시 token 마스킹 권장 (M5+ 고도화)

---

## 8. 관련 문서

- [`/CLAUDE.md`](../../CLAUDE.md) — "에이전트 ↔ 외부 도구 운영 원칙"
- [`mcp/CLAUDE.md`](../CLAUDE.md) §0 / §2.2 — thin bridge / API-client 패턴
- [`agents/primary/resources/wiki-authoring-guide.md`](../../agents/primary/resources/wiki-authoring-guide.md) — P 의 wiki 작성 가이드 (LLM 컨텍스트 embed)
- [`docs/proposal.md`](../../docs/proposal.md) §3.2 / §6.1단계 — P 가 wiki 작성 정책
- 이슈: #37
- 패턴 reference: `mcp/issue-tracker/` (#36)
