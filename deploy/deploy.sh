#!/usr/bin/env bash
# 서버에서 실행: git pull → 이미지 빌드 → 재시작 → 상태 확인
set -euo pipefail
cd "$(dirname "$0")/.."
git pull --ff-only
cd deploy
docker compose up -d --build
docker exec recycle-ollama ollama list | grep -q clef-flash || docker exec recycle-ollama ollama pull clef-flash
for i in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:11010/health >/dev/null 2>&1; then
    curl -sS http://127.0.0.1:11010/health; echo
    exit 0
  fi
  sleep 2
done
echo "앱이 응답하지 않습니다. 로그: docker logs --tail 80 recycle-app" >&2
exit 1
