# syntax=docker/dockerfile:1
#
# Primary 에이전트 이미지 — self-hosted OSS 경로.
#
# 베이스: python:3.13-slim (langgraph-api / proprietary runtime 의존 없음).
# 런타임: FastAPI + uvicorn. 엔드포인트는 primary_agent.server:app 에서 정의.
# 영속: OSS langgraph-checkpoint-postgres (AsyncPostgresSaver) 를 server.lifespan
#       에서 wiring. DATABASE_URI 환경변수로 주입.
#
# 빌드 (레포 루트에서):
#   docker build -f agents/primary/Dockerfile -t dev-team/primary:latest .
#
# 런타임 변수:
#   ANTHROPIC_API_KEY  (필수, overrides/primary.yaml 통해 주입)
#   DATABASE_URI       (선택, 미설정 시 in-memory)
#
# 빌드 전략 전반은 docs/agent-runtime.md §3 참조.

FROM python:3.13-slim

# 시스템 빌드 의존성 (psycopg 바이너리 / httpx C 확장 등 wheel 에서 처리되지만
# 일부 환경에서 필요할 수 있어 최소 도구 설치)
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# pip 캐시 크기 최소화 + byte-compile 생략 (이미지 용량 감축)
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# -- 1) shared 패키지 설치 (primary 보다 먼저 — dev-team-shared 의존 해소) --
COPY shared /app/shared
RUN pip install -e /app/shared

# -- 2) primary 패키지 설치 --
#    workspace root pyproject.toml 이 없으므로 [tool.uv.sources] 블록 제거 후 설치.
#    shared 는 위에서 이미 등록되어 `dev-team-shared` 의존은 PyPI lookup 없이 해소됨.
COPY agents/primary /app/primary
RUN sed -i '/^\[tool\.uv\.sources\]/,/^$/d' /app/primary/pyproject.toml \
 && pip install -e /app/primary

WORKDIR /app/primary
EXPOSE 8000

# FastAPI 서버 기동. 재시작 시 lifespan 이 Postgres checkpointer 재설정.
CMD ["uvicorn", "primary_agent.server:app", "--host", "0.0.0.0", "--port", "8000"]
