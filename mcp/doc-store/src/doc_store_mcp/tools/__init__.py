"""tools/ — MCP 도구 등록.

본 패키지를 import 하면 각 collection 모듈이 module-level `@mcp.tool()` 데코레이터로
자동 등록됨. 새 collection 추가 시 본 파일에 import 1줄 추가.
"""

# noqa: F401  # imports below are for side-effect (decorator registration)
from doc_store_mcp.tools import (
    agent_item,
    agent_session,
    agent_task,
    issue,
    wiki_page,
)

__all__: list[str] = []
