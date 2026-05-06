"""공유 컨텍스트 — repo 식별 + token + git binary 호출 helper.

도메인별 ops (현재 PageOps 만, 향후 확장) 가 공유.
"""

from __future__ import annotations


class _Ctx:
    """ops 들이 공유하는 런타임 자원.

    `wiki_url` 은 token 임베드된 HTTPS URL — clone / push 시 인증.
    워크디렉터리는 매 호출마다 임시 디렉터리를 새로 만들어 token leak 방지.
    """

    def __init__(
        self,
        *,
        owner: str,
        repo: str,
        token: str,
        author_name: str = "Wiki MCP",
        author_email: str = "wiki-mcp@dev-team.local",
    ) -> None:
        self.owner = owner
        self.repo = repo
        self.token = token
        self.author_name = author_name
        self.author_email = author_email

    @property
    def wiki_url(self) -> str:
        """token 임베드된 HTTPS clone URL.

        주의: workdir cleanup 안 하면 .git/config 에 token 남음. 호출자가 매번
        임시 dir 사용 + 작업 후 rmtree.
        """
        return (
            f"https://x-access-token:{self.token}"
            f"@github.com/{self.owner}/{self.repo}.wiki.git"
        )


__all__ = ["_Ctx"]
