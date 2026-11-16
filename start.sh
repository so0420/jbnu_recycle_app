#!/usr/bin/env bash
# 리사이클 서버 켜기 (앱 + AI). 사용: ~/projects/recycle/start.sh
set -euo pipefail
cd "$(dirname "$0")/deploy"
docker compose up -d          # 꺼져 있던 컨테이너를 다시 켠다 (이미지는 새로 만들지 않음)
echo "앱이 뜨기를 기다리는 중…"
for i in $(seq 1 90); do
  if curl -fsS http://127.0.0.1:11010/health >/dev/null 2>&1; then
    curl -sS http://127.0.0.1:11010/health; echo
    echo "켜졌어요: https://recycle.so4.kr"
    exit 0
  fi
  sleep 2
done
echo "3분 안에 응답이 없어요. 로그: docker logs --tail 80 recycle-app" >&2
exit 1
