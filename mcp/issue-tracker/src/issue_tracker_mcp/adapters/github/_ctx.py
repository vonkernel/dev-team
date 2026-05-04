"""공유 컨텍스트 — http 클라이언트 + repo 식별 + project_id lazy 캐시.

도메인별 ops (`IssueOps` / `StatusOps` / `TypeOps` / `FieldOps`) 가 같은 인스턴스를
공유. project_id 는 board 자체가 안 바뀌므로 영구 캐시 — 어떤 ops 가 먼저 호출
되든 1회만 GraphQL fetch.
"""

from __future__ import annotations

import httpx

from issue_tracker_mcp.adapters.github._http import GitHubGraphQLError, graphql


class _Ctx:
    """ops 들이 공유하는 런타임 자원."""

    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        owner: str,
        repo: str,
        project_number: int,
    ) -> None:
        self.http = http
        self.owner = owner
        self.repo = repo
        self.project_number = project_number
        self._project_id: str | None = None

    async def project_id(self) -> str:
        """board 의 GraphQL node id. 영구 캐시."""
        if self._project_id is not None:
            return self._project_id

        # owner 가 user 인지 organization 인지 미상 — 두 path 시도.
        query = """
        query($login: String!, $number: Int!) {
          organization(login: $login) {
            projectV2(number: $number) { id }
          }
          user(login: $login) {
            projectV2(number: $number) { id }
          }
        }
        """
        try:
            data = await graphql(
                self.http, query,
                {"login": self.owner, "number": self.project_number},
            )
        except GitHubGraphQLError as e:
            # organization / user 한쪽이 NOT_FOUND 인 게 정상 — partial data 사용.
            if e.data:
                data = e.data
            else:
                raise

        project = (data.get("organization") or {}).get("projectV2") or (
            data.get("user") or {}
        ).get("projectV2")
        if project is None:
            raise RuntimeError(
                f"Project v2 not found: owner={self.owner} number={self.project_number}",
            )
        self._project_id = str(project["id"])
        return self._project_id


__all__ = ["_Ctx"]
