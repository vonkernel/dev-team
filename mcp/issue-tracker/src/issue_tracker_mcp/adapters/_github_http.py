"""GitHub 어댑터의 HTTP / GraphQL 통신 헬퍼.

httpx 직접 사용 (SDK 미사용 — Projects v2 가 GraphQL only 라 SDK 도 wrapping
수준, 의존성 최소화 정책). 본 모듈은 wire-level 만, 도메인 매핑은 github.py.
"""

from __future__ import annotations

from typing import Any

import httpx

REST_BASE = "https://api.github.com"
GRAPHQL_URL = "https://api.github.com/graphql"


class GitHubAPIError(RuntimeError):
    """REST / GraphQL 호출 실패. 호출자가 status_code / payload 로 분기."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(f"GitHub API {status_code}: {detail[:300]}")
        self.status_code = status_code
        self.detail = detail


class GitHubGraphQLError(RuntimeError):
    """GraphQL 응답에 errors 가 있는 경우."""

    def __init__(self, errors: list[dict[str, Any]]) -> None:
        super().__init__(f"GraphQL errors: {errors}")
        self.errors = errors


def make_client(token: str, timeout: float = 30.0) -> httpx.AsyncClient:
    """공통 헤더가 박힌 httpx 클라이언트.

    `Authorization: Bearer` + GitHub API version 헤더. lifespan 에서 1회 생성
    후 어댑터에 주입.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "dev-team-issue-tracker-mcp/0.1",
    }
    return httpx.AsyncClient(headers=headers, timeout=timeout)


async def rest_request(
    http: httpx.AsyncClient,
    method: str,
    path: str,
    *,
    json: Any = None,
    params: dict[str, Any] | None = None,
) -> Any:
    """REST 호출. 2xx 면 JSON 반환 (204 면 None), 그 외 GitHubAPIError."""
    url = f"{REST_BASE}{path}"
    response = await http.request(method, url, json=json, params=params)
    if response.status_code == 204:
        return None
    if 200 <= response.status_code < 300:
        return response.json() if response.content else None
    raise GitHubAPIError(response.status_code, response.text)


async def graphql(
    http: httpx.AsyncClient,
    query: str,
    variables: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """GraphQL 호출. errors 면 GitHubGraphQLError, 아니면 data dict 반환."""
    body = {"query": query, "variables": variables or {}}
    response = await http.post(GRAPHQL_URL, json=body)
    if response.status_code != 200:
        raise GitHubAPIError(response.status_code, response.text)
    payload = response.json()
    if payload.get("errors"):
        raise GitHubGraphQLError(payload["errors"])
    data = payload.get("data") or {}
    return data  # type: ignore[no-any-return]


__all__ = [
    "GRAPHQL_URL",
    "GitHubAPIError",
    "GitHubGraphQLError",
    "REST_BASE",
    "graphql",
    "make_client",
    "rest_request",
]
