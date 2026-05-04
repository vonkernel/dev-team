"""IssueTracker MCP — entry point.

import side-effect 로 모든 도구를 mcp 인스턴스에 등록한 뒤 streamable HTTP 서버 기동.
"""

from __future__ import annotations

import logging

from issue_tracker_mcp import tools as _tools  # noqa: F401  (registers tools)
from issue_tracker_mcp.mcp_instance import mcp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("starting issue-tracker-mcp (streamable HTTP)")
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()


__all__ = ["main"]
