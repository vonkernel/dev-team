"""env 기반 설정. lifespan 에서 1회 로드 후 어댑터에 주입."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """IssueTracker MCP 서버 설정.

    env 우선순위 (Pydantic Settings 표준): env var > .env > 기본값.

    Status enum ↔ board option 매핑은 **adapter 부팅 시 board 에서 조회 + 이름
    정규화 매칭**. 별도 env 매핑 X — MCP 의 본질이 실 도구의 bridge 이므로 SoT
    는 도구(board) 자체.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        # 빈 string env 는 unset 으로 취급 → default 값 사용. compose 가
        # `${VAR}` 를 unset 변수에 빈 string 으로 expand 하는 케이스 방어.
        env_ignore_empty=True,
    )

    # 어댑터 선택 — factory.py 에서 사용
    issue_tracker_type: str = Field(
        default="github",
        description="구현체 식별자 (github / jira / linear / ...)",
    )

    # GitHub 어댑터 전용 — type=github 일 때만 의미
    github_token: str = Field(
        default="",
        description="Fine-grained PAT, scope: repo + project",
    )
    github_target_owner: str = Field(
        default="",
        description="대상 저장소 owner (user/org)",
    )
    github_target_repo: str = Field(
        default="",
        description="대상 저장소 name",
    )
    github_project_number: int = Field(
        default=0,
        description="Project v2 number (board 식별)",
    )

    # streamable HTTP 서버 포트 (컨테이너 내부)
    http_port: int = 8000


__all__ = ["Settings"]
