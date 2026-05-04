"""GitHub Issues + Projects v2 어댑터 패키지.

mcp/CLAUDE.md §0 (thin bridge) + §2.2 (API-client 패턴) 준수.

도메인별 모듈 분할 (SRP):
- `adapter`         — IssueTracker 컴포지트 진입점 (외부 노출)
- `issue` / `status` / `type` / `field` — 4 도메인 ops (각 ABC 구현)
- `_ctx`            — 공유 런타임 (http + repo 식별 + project_id 캐시)
- `_http`           — REST + GraphQL helper
- `_field_resolver` — board field name → id (도메인 ops 들이 공유)
- `_field_options`  — single-select option 조작 (status/type 가 공유)
- `_project_items`  — Project board item 조작 (issue ops 가 사용)
"""

from issue_tracker_mcp.adapters.github.adapter import GitHubIssueTrackerAdapter

__all__ = ["GitHubIssueTrackerAdapter"]
