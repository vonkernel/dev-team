#!/usr/bin/env bash
#
# Neo4j 초기화 스크립트 (뼈대)
#
# 현재 범위: 접속 확인만.
# 스키마(제약/인덱스) 설계는 별도 결정 후 이 스크립트에 추가 예정.
#
# 용도:
#   1) docker compose의 one-shot init 서비스에서 자동 실행
#   2) 수동 실행:
#        NEO4J_URI=bolt://localhost:7687 \
#        NEO4J_USER=neo4j \
#        NEO4J_PASSWORD=devteam_neo4j \
#        bash infra/init/neo4j-init.sh
#
# 요구 바이너리: cypher-shell (neo4j:5 이미지에 기본 포함)
#
# 참고: Neo4j Community 에디션은 기본 DB(\`neo4j\`)가 자동 생성되며
#        추가 DB 생성은 Enterprise 에디션 기능이므로 이 스크립트에서 다루지 않는다.

set -euo pipefail

NEO4J_URI="${NEO4J_URI:-bolt://neo4j:7687}"
NEO4J_USER="${NEO4J_USER:-neo4j}"
NEO4J_PASSWORD="${NEO4J_PASSWORD:?NEO4J_PASSWORD is required}"

echo "[neo4j-init] checking connectivity to ${NEO4J_URI} ..."
cypher-shell -a "${NEO4J_URI}" -u "${NEO4J_USER}" -p "${NEO4J_PASSWORD}" "RETURN 1 AS ok;" >/dev/null

echo "[neo4j-init] connection OK. (schema will be added later when designed)"
