#!/usr/bin/env bash
#
# PostgreSQL 초기화 스크립트 (뼈대)
#
# 현재 범위: 접속 확인 + 애플리케이션 DB(`dev_team`) 존재 보장 + langgraph DB 존재 보장.
# 테이블/인덱스/스키마 설계는 별도 결정 후 이 스크립트에 추가 예정.
#
# 배경 (자세한 내용은 docs/proposal-main.md, issue #20):
#   본 프로젝트는 저장소를 둘로 분리하지 않고 단일 Postgres 인스턴스에
#   **DB 2개를 분리 운영** 한다:
#     1) `langgraph`  — langgraph-checkpoint-postgres (AsyncPostgresSaver) 전용. 라이브러리가 직접 스키마/마이그레이션 관리.
#     2) `dev_team`   — 애플리케이션 데이터 (Doc Store 5 collection — wiki_pages / issues / agent_tasks / agent_sessions / agent_items). 정형 RDB + 일부 JSONB 보조.
#
# 용도:
#   1) docker compose 의 one-shot init 서비스에서 자동 실행
#   2) 수동 실행:
#        POSTGRES_HOST=localhost POSTGRES_PORT=5432 \
#        POSTGRES_USER=devteam POSTGRES_PASSWORD=devteam_postgres \
#        POSTGRES_DB=langgraph APP_DB=dev_team \
#        bash infra/init/postgres-init.sh
#
# 요구 바이너리: psql (postgres:17 이미지에 포함)

set -euo pipefail

POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:?POSTGRES_USER is required}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"
LG_DB="${POSTGRES_DB:-langgraph}"
APP_DB="${APP_DB:-dev_team}"

export PGPASSWORD="${POSTGRES_PASSWORD}"

echo "[postgres-init] checking connectivity to ${POSTGRES_HOST}:${POSTGRES_PORT} ..."
psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d postgres \
  -c "SELECT 1;" >/dev/null

# 애플리케이션 DB(APP_DB) 존재 보장 — 없으면 생성.
# langgraph DB 는 postgres 컨테이너의 POSTGRES_DB 환경변수로 최초 부팅 시 자동 생성됨.
echo "[postgres-init] ensuring app database '${APP_DB}' exists ..."
psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d postgres -tc \
  "SELECT 1 FROM pg_database WHERE datname = '${APP_DB}';" | grep -q 1 || \
psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d postgres -c \
  "CREATE DATABASE \"${APP_DB}\" OWNER \"${POSTGRES_USER}\";"

echo "[postgres-init] OK. Databases: '${LG_DB}' (langgraph-api), '${APP_DB}' (application document storage)."
echo "[postgres-init] tables/indexes will be added later when schemas are designed."
