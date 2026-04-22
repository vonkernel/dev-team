#!/usr/bin/env bash
#
# MongoDB 초기화 스크립트 (뼈대)
#
# 현재 범위: 접속 확인 + app DB 참조까지.
# 컬렉션/인덱스 설계는 별도 결정 후 이 스크립트에 추가 예정.
#
# 용도:
#   1) docker compose의 one-shot init 서비스에서 자동 실행
#   2) 수동 실행:
#        MONGO_HOST=localhost MONGO_PORT=27017 \
#        MONGO_INITDB_ROOT_USERNAME=root \
#        MONGO_INITDB_ROOT_PASSWORD=devteam_mongo \
#        MONGO_APP_DB=dev_team \
#        bash infra/init/mongo-init.sh
#
# 요구 바이너리: mongosh (mongo:8 이미지에 기본 포함)
#
# 참고: MongoDB 는 데이터베이스를 최초 쓰기 시점에 자동 생성한다.
#        따라서 별도의 "DB 생성" 단계는 필요 없고, 이 스크립트는 접속 확인만 수행한다.

set -euo pipefail

MONGO_HOST="${MONGO_HOST:-mongodb}"
MONGO_PORT="${MONGO_PORT:-27017}"
MONGO_USER="${MONGO_INITDB_ROOT_USERNAME:-root}"
MONGO_PASS="${MONGO_INITDB_ROOT_PASSWORD:?MONGO_INITDB_ROOT_PASSWORD is required}"
APP_DB="${MONGO_APP_DB:-dev_team}"

echo "[mongo-init] checking connectivity to ${MONGO_HOST}:${MONGO_PORT} (app db: ${APP_DB}) ..."
mongosh --quiet \
  --host "${MONGO_HOST}" --port "${MONGO_PORT}" \
  -u "${MONGO_USER}" -p "${MONGO_PASS}" \
  --authenticationDatabase admin \
  --eval "db.getSiblingDB('${APP_DB}').runCommand({ ping: 1 }).ok" >/dev/null

echo "[mongo-init] connection OK. (collections/indexes will be added later when designed)"
