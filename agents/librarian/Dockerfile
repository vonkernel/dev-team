# syntax=docker/dockerfile:1
#
# Librarian (L) 에이전트 이미지 — self-hosted OSS 경로.
#
# 베이스: python:3.13-slim
# 런타임: FastAPI + uvicorn. 엔드포인트는 librarian_agent.server:app 에서 정의.
# Backend MCP: Doc Store (DOC_STORE_MCP_URL).
# 영속: AsyncPostgresSaver (Postgres `langgraph` DB) — DATABASE_URI.
#
# 빌드 (레포 루트에서):
#   docker build -f agents/librarian/Dockerfile -t dev-team/librarian:latest .
#
# 런타임 변수:
#   ANTHROPIC_API_KEY       (필수, overrides/librarian.yaml 통해 주입)
#   DOC_STORE_MCP_URL       (필수, 예: http://doc-store-mcp:8000/mcp)
#   DATABASE_URI            (선택, 미설정 시 in-memory checkpointer)

FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# -- 1) shared 패키지 설치 --
COPY shared /app/shared
RUN pip install -e /app/shared

# -- 2) librarian 패키지 설치 --
COPY agents/librarian /app/librarian
RUN sed -i '/^\[tool\.uv\.sources\]/,/^$/d' /app/librarian/pyproject.toml \
 && pip install -e /app/librarian

WORKDIR /app/librarian
EXPOSE 8000

CMD ["uvicorn", "librarian_agent.server:app", "--host", "0.0.0.0", "--port", "8000"]
