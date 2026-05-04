# syntax=docker/dockerfile:1
#
# Document DB MCP 서버 이미지.
#
# 베이스: python:3.13-slim
# 런타임: FastMCP (mcp SDK) 위 streamable HTTP transport (uvicorn).
# DB: 단일 Postgres 인스턴스의 dev_team DB (langgraph DB 와 분리, 이슈 #20).
#
# 빌드 (레포 루트에서):
#   docker build -f mcp/doc-store/Dockerfile -t dev-team/doc-store-mcp:latest .
#
# 런타임 변수:
#   DATABASE_URI         dev_team DB DSN (compose 가 주입)
#   AUTO_MIGRATE         true (기본). 부팅 시 yoyo 마이그레이션 자동 적용

FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# shared 먼저 (dev-team-shared 의존 해소 — schemas + tool_names + DocStoreClient)
COPY shared /app/shared
RUN pip install -e /app/shared

COPY mcp/doc-store /app/doc-store
RUN sed -i '/^\[tool\.uv\.sources\]/,/^$/d' /app/doc-store/pyproject.toml \
 && pip install -e /app/doc-store

WORKDIR /app/doc-store
EXPOSE 8000

CMD ["python", "-m", "doc_store_mcp.server"]
