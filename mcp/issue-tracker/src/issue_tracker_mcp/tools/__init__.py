"""issue-tracker-mcp 도구 등록 트리거.

각 모듈을 import 하는 것만으로 module-level `@mcp.tool()` 데코레이터가 실행
되어 도구가 등록 (mcp/CLAUDE.md §1.3).
"""

from issue_tracker_mcp.tools import (  # noqa: F401  side-effect imports
    field,
    issue,
    status,
    type,
)
