#!/usr/bin/env bash
#
# Neo4j 스키마 초기화 스크립트
#
# 적용 대상: proposal.md §4.1 (Semantic Layer)
# - 노드: Interface, Class, PublicMethod, Module, Task, Feature, BugReport
# - 제약조건 및 인덱스는 CREATE ... IF NOT EXISTS 로 idempotent
#
# 용도:
#   1) docker compose의 one-shot init 서비스에서 자동 실행
#   2) 수동 실행도 가능 — 필요한 env만 주입
#        NEO4J_URI=bolt://localhost:7687 \
#        NEO4J_USER=neo4j \
#        NEO4J_PASSWORD=devteam_neo4j \
#        bash infra/init/neo4j-init.sh
#
# 요구 바이너리: cypher-shell (neo4j:5 이미지에 기본 포함)

set -euo pipefail

NEO4J_URI="${NEO4J_URI:-bolt://neo4j:7687}"
NEO4J_USER="${NEO4J_USER:-neo4j}"
NEO4J_PASSWORD="${NEO4J_PASSWORD:?NEO4J_PASSWORD is required}"

echo "[neo4j-init] applying schema to ${NEO4J_URI} ..."

cypher-shell -a "${NEO4J_URI}" -u "${NEO4J_USER}" -p "${NEO4J_PASSWORD}" <<'CYPHER'
// --- 제약조건 (고유성) ---
CREATE CONSTRAINT interface_name_unique  IF NOT EXISTS FOR (i:Interface)    REQUIRE i.name IS UNIQUE;
CREATE CONSTRAINT class_fqn_unique       IF NOT EXISTS FOR (c:Class)        REQUIRE c.fqn  IS UNIQUE;
CREATE CONSTRAINT module_path_unique     IF NOT EXISTS FOR (m:Module)       REQUIRE m.path IS UNIQUE;
CREATE CONSTRAINT task_id_unique         IF NOT EXISTS FOR (t:Task)         REQUIRE t.id   IS UNIQUE;
CREATE CONSTRAINT feature_id_unique      IF NOT EXISTS FOR (f:Feature)      REQUIRE f.id   IS UNIQUE;
CREATE CONSTRAINT bugreport_id_unique    IF NOT EXISTS FOR (b:BugReport)    REQUIRE b.id   IS UNIQUE;

// --- 인덱스 (non-unique, 조회 성능용) ---
CREATE INDEX publicmethod_signature IF NOT EXISTS FOR (p:PublicMethod) ON (p.signature);
CREATE INDEX class_module            IF NOT EXISTS FOR (c:Class)        ON (c.module);
CYPHER

echo "[neo4j-init] done."
