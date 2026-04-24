# syntax=docker/dockerfile:1
#
# User Gateway 이미지 — 멀티스테이지.
#   1) node:22-slim        → Vite 프로덕션 빌드 (frontend/dist)
#   2) python:3.13-slim    → FastAPI 서버 + shared + user-gateway 설치,
#                            1) 결과를 /app/ug/static 으로 복사해 정적 서빙
#
# 빌드 (레포 루트에서):
#   docker build -f user-gateway/Dockerfile -t dev-team/user-gateway:latest .

# ────────────────────────────────────────────────────────────────
#  Stage 1 — Frontend 빌드 (Vite)
# ────────────────────────────────────────────────────────────────
FROM node:22-slim AS frontend-build

WORKDIR /fe

# lockfile 먼저 복사 → deps 설치 레이어 캐시 유효 활용
COPY user-gateway/frontend/package.json user-gateway/frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY user-gateway/frontend ./
RUN npm run build
# 산출물: /fe/dist

# ────────────────────────────────────────────────────────────────
#  Stage 2 — Python 백엔드
# ────────────────────────────────────────────────────────────────
FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
 && rm -rf /var/lib/apt/lists/*

ENV PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# 1) shared 먼저 설치 (user-gateway 의 dev-team-shared 의존 해소)
COPY shared /app/shared
RUN pip install -e /app/shared

# 2) user-gateway 백엔드 설치.
#    Docker 안엔 workspace 루트 pyproject.toml 이 없으므로 [tool.uv.sources] 블록 제거 후 설치.
COPY user-gateway /app/ug
RUN sed -i '/^\[tool\.uv\.sources\]/,/^$/d' /app/ug/pyproject.toml \
 && pip install -e /app/ug

# 3) Vite 빌드 결과를 정적 서빙 경로로 복사 (server.py 의 _DEFAULT_STATIC_DIR)
COPY --from=frontend-build /fe/dist /app/ug/static

WORKDIR /app/ug
EXPOSE 8000

CMD ["uvicorn", "user_gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
