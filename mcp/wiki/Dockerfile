# syntax=docker/dockerfile:1
#
# Wiki MCP 서버 이미지.
#
# 베이스: python:3.13-slim + git binary (subprocess 호출용)
# 런타임: FastMCP (mcp SDK) 위 streamable HTTP transport (uvicorn)
# Backend: GitHub Wiki — 별 git repo (`<owner>/<repo>.wiki.git`) clone/commit/push
#
# 빌드 (레포 루트에서):
#   docker build -f mcp/wiki/Dockerfile -t dev-team/wiki-mcp:latest .
#
# 런타임 변수 (compose 가 .env 통해 주입):
#   WIKI_TYPE                github (기본)
#   GITHUB_TOKEN             PAT (`repo` scope 가 wiki 권한 포함)
#   GITHUB_TARGET_OWNER      대상 저장소 owner
#   GITHUB_TARGET_REPO       대상 저장소 name (.wiki.git suffix 자동)

FROM python:3.13-slim

# git: subprocess 로 wiki repo clone/commit/push
# ca-certificates: HTTPS clone 시 cert 검증
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        git \
    && rm -rf /var/lib/apt/lists/*

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# shared 먼저 (dev-team-shared 의존 해소)
COPY shared /app/shared
RUN pip install -e /app/shared

COPY mcp/wiki /app/wiki
RUN sed -i '/^\[tool\.uv\.sources\]/,/^$/d' /app/wiki/pyproject.toml \
 && pip install -e /app/wiki

WORKDIR /app/wiki
EXPOSE 8000

CMD ["python", "-m", "wiki_mcp.server"]
