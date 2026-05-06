"""Wiki MCP — entry point."""

from __future__ import annotations

import logging

from wiki_mcp import tools as _tools  # noqa: F401  (registers tools)
from wiki_mcp.mcp_instance import mcp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("starting wiki-mcp (streamable HTTP)")
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()


__all__ = ["main"]
