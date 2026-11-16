#!/usr/bin/env bash
# 서버에서 실행: git pull → 이미지 빌드 → 재시작 → 상태 확인
set -euo pipefail
cd "$(dirname "$0")/.."
git pull --ff-only
cd deploy
docker compose up -d --build
docker exec recycle-ollama ollama list | grep -q clef-flash || docker exec recycle-ollama ollama pull clef-flash
# 데이터가 바뀐 배포는 시작할 때 전국 수거장 21만 곳을 다시 넣으므로 넉넉히 기다린다 (최대 5분)
for i in $(seq 1 150); do
  if curl -fsS http://127.0.0.1:11010/health >/dev/null 2>&1; then
    curl -sS http://127.0.0.1:11010/health; echo
    exit 0
  fi
  sleep 2
done
echo "앱이 응답하지 않습니다. 로그: docker logs --tail 80 recycle-app" >&2
exit 1
