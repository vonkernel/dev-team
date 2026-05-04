# syntax=docker/dockerfile:1
#
# Chronicler (CHR) 컨테이너 — 단일 Python 스크립트.
# 베이스: python:3.13-slim
# 책임: Valkey Streams consumer + Document DB MCP 클라이언트
#
# 빌드 (레포 루트에서):
#   docker build -f chronicler/Dockerfile -t dev-team/chronicler:latest .

FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# shared 먼저 (chronicler 의 dev-team-shared 의존 해소)
COPY shared /app/shared
RUN pip install -e /app/shared

# chronicler 패키지
COPY chronicler /app/chronicler
RUN sed -i '/^\[tool\.uv\.sources\]/,/^$/d' /app/chronicler/pyproject.toml \
 && pip install -e /app/chronicler

WORKDIR /app/chronicler

CMD ["python", "-m", "chronicler.main"]
