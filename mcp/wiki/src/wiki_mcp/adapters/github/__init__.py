"""GitHub Wiki (별 git repo) 어댑터 패키지.

mcp/CLAUDE.md §0 (thin bridge) + §2.2 (API-client 패턴) 준수.
도메인별 모듈 분할 (SRP).
"""

from wiki_mcp.adapters.github.adapter import GitHubWikiAdapter

__all__ = ["GitHubWikiAdapter"]
