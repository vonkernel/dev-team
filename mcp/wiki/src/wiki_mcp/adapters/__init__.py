"""Wiki 어댑터 — ABC + 구현체."""

from wiki_mcp.adapters.base import PageOps, Wiki
from wiki_mcp.adapters.github import GitHubWikiAdapter

__all__ = ["GitHubWikiAdapter", "PageOps", "Wiki"]
