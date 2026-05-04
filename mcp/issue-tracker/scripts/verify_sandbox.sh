#!/usr/bin/env bash
#
# IssueTracker MCP 1차 동작 검증 — sandbox (vonkernel/guestbook).
#
# 사용:
#   bash mcp/issue-tracker/scripts/verify_sandbox.sh
#
# 사전 조건 (.env 의 다음 키):
#   GITHUB_TOKEN              fine-grained PAT (Issues + Projects 권한)
#   GITHUB_TARGET_OWNER       vonkernel
#   GITHUB_TARGET_REPO        guestbook
#   GITHUB_PROJECT_NUMBER     board URL 끝 숫자
#
# 동작:
#   1. issue-tracker-mcp 컨테이너 부팅 (docker compose --profile mcp up -d)
#   2. mcp/issue-tracker 의 venv 에서 verify_sandbox.py 실행
#   3. 8 시나리오 통과 시 ALL PASS, 검증용 이슈는 close 처리
#   4. 컨테이너는 부팅 상태 유지 (정리 원하면 마지막 안내 명령 실행)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/infra/docker-compose.yml"
ENV_FILE="$REPO_ROOT/.env"
MCP_DIR="$REPO_ROOT/mcp/issue-tracker"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERR: .env not found at $ENV_FILE" >&2
  exit 1
fi

# .env 의 GITHUB_PROJECT_NUMBER 확인 (값 노출 X)
if ! awk -F= '/^GITHUB_PROJECT_NUMBER=/ && length($2) > 0 {found=1} END{exit !found}' "$ENV_FILE"; then
  echo "ERR: GITHUB_PROJECT_NUMBER missing or empty in .env" >&2
  exit 1
fi

echo "==> 1. issue-tracker-mcp 컨테이너 부팅 (rebuild)"
( cd "$REPO_ROOT/infra" && docker compose --profile mcp up -d --build issue-tracker-mcp )

echo "==> 2. 부팅 대기 (3s)"
sleep 3

echo "==> 3. health check (logs)"
docker compose -f "$COMPOSE_FILE" logs issue-tracker-mcp --tail 5

echo "==> 4. 검증 스크립트 실행"
( cd "$MCP_DIR" && uv run python scripts/verify_sandbox.py )

echo
echo "==================================================================="
echo "검증 완료. 컨테이너는 부팅 상태 유지 — http://localhost:9101/mcp"
echo
echo "정리하려면:"
echo "  docker compose -f $COMPOSE_FILE --profile mcp down issue-tracker-mcp"
echo "==================================================================="
