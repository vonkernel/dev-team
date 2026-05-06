#!/usr/bin/env bash
#
# Librarian (L) 1차 통합 검증 — A2A SendStreamingMessage 자연어 요청.
#
# 사용:
#   bash agents/librarian/scripts/verify_sandbox.sh
#
# 사전 조건:
#   .env 의 ANTHROPIC_API_KEY (Primary 와 공유)
#   doc-store-mcp 컨테이너 부팅 (--profile mcp 또는 agents)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/infra/docker-compose.yml"
AGENT_DIR="$REPO_ROOT/agents/librarian"

if ! awk -F= '$1=="ANTHROPIC_API_KEY" && length($2)>0 {found=1} END{exit !found}' "$REPO_ROOT/.env"; then
  echo "ERR: ANTHROPIC_API_KEY missing/empty in .env" >&2
  exit 1
fi

echo "==> 1. doc-store-mcp + librarian 부팅 (rebuild)"
( cd "$REPO_ROOT/infra" && docker compose --profile agents up -d --build doc-store-mcp librarian )

echo "==> 2. 부팅 대기 (5s)"
sleep 5

echo "==> 3. health check (logs)"
docker compose -f "$COMPOSE_FILE" logs librarian --tail 5

echo "==> 4. 자연어 ReAct 시나리오 실행"
( cd "$AGENT_DIR" && uv run python scripts/verify_sandbox.py )

echo
echo "==================================================================="
echo "검증 완료. librarian — http://localhost:9002/a2a/librarian"
echo
echo "정리:"
echo "  docker compose -f $COMPOSE_FILE --profile agents down librarian"
echo "==================================================================="
