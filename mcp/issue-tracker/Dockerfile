# syntax=docker/dockerfile:1
#
# IssueTracker MCP 서버 이미지.
#
# 베이스: python:3.13-slim
# 런타임: FastMCP (mcp SDK) 위 streamable HTTP transport (uvicorn).
# Backend: GitHub Issues + Projects v2 (REST + GraphQL).
#
# 빌드 (레포 루트에서):
#   docker build -f mcp/issue-tracker/Dockerfile -t dev-team/issue-tracker-mcp:latest .
#
# 런타임 변수 (compose 가 주입):
#   ISSUE_TRACKER_TYPE        github (기본)
#   GITHUB_TOKEN              fine-grained PAT (scope: repo + project)
#   GITHUB_TARGET_OWNER       대상 저장소 owner
#   GITHUB_TARGET_REPO        대상 저장소 name
#   GITHUB_PROJECT_NUMBER     Project v2 number (board 식별)

FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# shared 먼저 (dev-team-shared 의존 해소)
COPY shared /app/shared
RUN pip install -e /app/shared

COPY mcp/issue-tracker /app/issue-tracker
RUN sed -i '/^\[tool\.uv\.sources\]/,/^$/d' /app/issue-tracker/pyproject.toml \
 && pip install -e /app/issue-tracker

WORKDIR /app/issue-tracker
EXPOSE 8000

CMD ["python", "-m", "issue_tracker_mcp.server"]
