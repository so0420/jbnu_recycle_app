#!/usr/bin/env bash
# recycle.so4.kr nginx 연결 (sudo 로 실행)
#   cd ~/projects/recycle && git pull && sudo bash deploy/nginx/install.sh
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
SITE=/etc/nginx/sites-available/recycle.so4.kr
[ "$(id -u)" -eq 0 ] || { echo "sudo 로 실행해 주세요: sudo bash $0" >&2; exit 1; }
[ -f /etc/nginx/snippets/cloudflare-allow.conf ] || { echo "/etc/nginx/snippets/cloudflare-allow.conf 가 없습니다" >&2; exit 1; }

STAMP=$(date +%Y%m%d%H%M%S)
HAD_SITE=0; [ -f "$SITE" ] && { HAD_SITE=1; cp "$SITE" "/tmp/recycle.so4.kr.bak.$STAMP"; }
HAD_LINK=0; [ -e /etc/nginx/sites-enabled/recycle.so4.kr ] && HAD_LINK=1
OLD_CONFD=""
if [ -f /etc/nginx/conf.d/recycle.conf ]; then          # 이전 방식(conf.d 분리) 정리
    OLD_CONFD="/tmp/recycle.conf.bak.$STAMP"
    mv /etc/nginx/conf.d/recycle.conf "$OLD_CONFD"
fi

cp "$DIR/recycle.so4.kr" "$SITE"
ln -sf "$SITE" /etc/nginx/sites-enabled/recycle.so4.kr

if ! nginx -t; then
    echo "설정 오류: 이전 상태로 되돌립니다" >&2
    if [ "$HAD_SITE" = 1 ]; then cp "/tmp/recycle.so4.kr.bak.$STAMP" "$SITE"; else rm -f "$SITE"; fi
    [ "$HAD_LINK" = 1 ] || rm -f /etc/nginx/sites-enabled/recycle.so4.kr
    [ -n "$OLD_CONFD" ] && mv "$OLD_CONFD" /etc/nginx/conf.d/recycle.conf
    nginx -t && systemctl reload nginx
    exit 1
fi
systemctl reload nginx
sleep 1

echo "--- 확인"
curl -s -o /dev/null -w "앱 (127.0.0.1:11010): %{http_code}\n" http://127.0.0.1:11010/health || true
curl -s -o /dev/null -w "https://recycle.so4.kr/health: %{http_code}\n" https://recycle.so4.kr/health || true
curl -s -o /dev/null "https://recycle.so4.kr/api/v1/places?lat=35.82&lng=127.14&radius=100" || true
sleep 1
echo "recycle_access.log 마지막 줄 (주소·좌표가 없어야 정상):"
tail -n 1 /var/log/nginx/recycle_access.log 2>/dev/null || echo "(아직 기록 없음)"
if tail -n 1 /var/log/nginx/recycle_access.log 2>/dev/null | grep -qE "lat=|/api/"; then
    echo "경고: 로그에 주소·좌표가 남았습니다" >&2
fi
echo "완료: https://recycle.so4.kr"
