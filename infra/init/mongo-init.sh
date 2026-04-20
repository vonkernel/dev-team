#!/usr/bin/env bash
#
# MongoDB 초기화 스크립트
#
# 적용 대상: proposal.md §4.2 (Episodic Layer)
#   컬렉션: tasks, sessions, items, technical_notes, design_alternatives
#   인덱스: 주요 조회 패턴(by_task, by_session, thread) 대응
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

set -euo pipefail

MONGO_HOST="${MONGO_HOST:-mongodb}"
MONGO_PORT="${MONGO_PORT:-27017}"
MONGO_USER="${MONGO_INITDB_ROOT_USERNAME:-root}"
MONGO_PASS="${MONGO_INITDB_ROOT_PASSWORD:?MONGO_INITDB_ROOT_PASSWORD is required}"
APP_DB="${MONGO_APP_DB:-dev_team}"

echo "[mongo-init] initializing database '${APP_DB}' on ${MONGO_HOST}:${MONGO_PORT} ..."

mongosh --quiet \
  --host "${MONGO_HOST}" --port "${MONGO_PORT}" \
  -u "${MONGO_USER}" -p "${MONGO_PASS}" \
  --authenticationDatabase admin \
  --eval "
const appDb = '${APP_DB}';
const cols = ['tasks', 'sessions', 'items', 'technical_notes', 'design_alternatives'];

const target = db.getSiblingDB(appDb);
const existing = target.getCollectionNames();

// 1) 컬렉션 생성 (idempotent)
cols.forEach(function (c) {
  if (!existing.includes(c)) {
    target.createCollection(c);
    print('[mongo-init] created collection: ' + c);
  } else {
    print('[mongo-init] exists: ' + c);
  }
});

// 2) 인덱스 (createIndex 는 동일 spec 이면 idempotent)
target.sessions.createIndex({ task_id: 1 });
target.items.createIndex({ task_id: 1 });
target.items.createIndex({ session_id: 1 });
target.items.createIndex({ prev_item_id: 1 });
target.items.createIndex({ task_id: 1, timestamp: 1 });
target.technical_notes.createIndex({ task_id: 1 });
target.design_alternatives.createIndex({ task_id: 1 });

print('[mongo-init] indexes applied.');
"

echo "[mongo-init] done."
