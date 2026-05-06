#!/usr/bin/env bash
#
# Wiki MCP 1차 동작 검증 — sandbox (vonkernel/guestbook 의 GitHub Wiki).
#
# 사용:
#   bash mcp/wiki/scripts/verify_sandbox.sh
#
# 사전 조건 (.env 의 다음 키):
#   GITHUB_TOKEN              PAT (`repo` scope 가 wiki 권한 포함)
#   GITHUB_TARGET_OWNER       vonkernel
#   GITHUB_TARGET_REPO        guestbook
#   (Wiki 활성화 — Settings → Features → Wikis 가 켜져있어야 함)
#
# 동작:
#   1. wiki-mcp 컨테이너 부팅 (rebuild)
#   2. mcp/wiki venv 에서 verify_sandbox.py 실행
#   3. 7 시나리오 통과 시 ALL PASS, 검증 페이지 자동 삭제
#   4. 컨테이너는 부팅 상태 유지

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/infra/docker-compose.yml"
ENV_FILE="$REPO_ROOT/.env"
MCP_DIR="$REPO_ROOT/mcp/wiki"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERR: .env not found at $ENV_FILE" >&2
  exit 1
fi

for key in GITHUB_TOKEN GITHUB_TARGET_OWNER GITHUB_TARGET_REPO; do
  if ! awk -F= -v k="$key" '$1==k && length($2)>0 {found=1} END{exit !found}' "$ENV_FILE"; then
    echo "ERR: $key missing or empty in .env" >&2
    exit 1
  fi
done

echo "==> 1. wiki-mcp 컨테이너 부팅 (rebuild)"
( cd "$REPO_ROOT/infra" && docker compose --profile mcp up -d --build wiki-mcp )

echo "==> 2. 부팅 대기 (3s)"
sleep 3

echo "==> 3. health check (logs)"
docker compose -f "$COMPOSE_FILE" logs wiki-mcp --tail 5

echo "==> 4. 검증 스크립트 실행"
( cd "$MCP_DIR" && uv run python scripts/verify_sandbox.py )

echo
echo "==================================================================="
echo "검증 완료. 컨테이너는 부팅 상태 유지 — http://localhost:9102/mcp"
echo
echo "정리하려면:"
echo "  docker compose -f $COMPOSE_FILE --profile mcp down wiki-mcp"
echo "==================================================================="
