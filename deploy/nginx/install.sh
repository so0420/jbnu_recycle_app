#!/usr/bin/env bash
# recycle.so4.kr nginx 연결 (sudo 로 실행)
#   sudo bash ~/projects/recycle/deploy/nginx/install.sh
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)/recycle.so4.kr"
[ "$(id -u)" -eq 0 ] || { echo "sudo 로 실행해 주세요: sudo bash $0" >&2; exit 1; }
cp "$SRC" /etc/nginx/sites-available/recycle.so4.kr
ln -sf /etc/nginx/sites-available/recycle.so4.kr /etc/nginx/sites-enabled/recycle.so4.kr
nginx -t
systemctl reload nginx
sleep 1
echo "--- 확인"
curl -s -o /dev/null -w "로컬 https: %{http_code}\n" --resolve recycle.so4.kr:443:127.0.0.1 -k https://recycle.so4.kr/health || true
echo "완료: https://recycle.so4.kr"
