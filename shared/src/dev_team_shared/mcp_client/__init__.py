"""MCP 클라이언트 헬퍼 — streamable HTTP 위.

CHR / 에이전트 (P / L 등) 가 다른 MCP 서버 호출 시 공용 사용. `mcp` SDK 위에
얇은 어댑터 — lifespan-friendly 사용 (생성자 주입 + aclose).

사용 예:

    async with StreamableMCPClient.connect("http://document-db-mcp:8000/mcp") as client:
        result = await client.call_tool("agent_task.create", {"doc": {...}})
"""

from dev_team_shared.mcp_client.client import StreamableMCPClient

__all__ = ["StreamableMCPClient"]
