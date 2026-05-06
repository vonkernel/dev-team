"""Wiki MCP SDK — schemas + 도구명 상수 + typed client.

server (mcp/wiki) / client (P 등) 공유 contract.
"""

from dev_team_shared.wiki._ops_client import PageClient
from dev_team_shared.wiki.client import WikiClient
from dev_team_shared.wiki.schemas import (
    PageCreate,
    PageRead,
    PageRef,
    PageUpdate,
)
from dev_team_shared.wiki.tool_names import PageTools

__all__ = [
    "PageClient",
    "PageCreate",
    "PageRead",
    "PageRef",
    "PageTools",
    "PageUpdate",
    "WikiClient",
]
