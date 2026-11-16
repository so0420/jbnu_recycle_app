#!/usr/bin/env bash
# 리사이클 서버 끄기 (앱 + AI). 사용: ~/projects/recycle/stop.sh
# 꺼 둔 동안 https://recycle.so4.kr 은 502 가 난다. 서버를 재부팅해도 꺼진 채로 남는다.
set -euo pipefail
cd "$(dirname "$0")/deploy"
docker compose stop
docker ps -a --filter name=recycle --format '{{.Names}}: {{.Status}}'
echo "꺼졌어요. 다시 켜려면: ~/projects/recycle/start.sh"
