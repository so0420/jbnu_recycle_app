#!/usr/bin/env bash
# recycle.so4.kr nginx 연결 (sudo 로 실행)
#   cd ~/projects/recycle && git pull && sudo bash deploy/nginx/install.sh
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
[ "$(id -u)" -eq 0 ] || { echo "sudo 로 실행해 주세요: sudo bash $0" >&2; exit 1; }
[ -f /etc/nginx/snippets/cloudflare-allow.conf ] || { echo "/etc/nginx/snippets/cloudflare-allow.conf 가 없습니다" >&2; exit 1; }

# 되돌릴 수 있게 기존 파일을 보관
STAMP=$(date +%Y%m%d%H%M%S)
for f in /etc/nginx/conf.d/recycle.conf /etc/nginx/sites-available/recycle.so4.kr; do
    [ -f "$f" ] && cp "$f" "/tmp/$(basename "$f").bak.$STAMP"
done

cp "$DIR/recycle.conf"   /etc/nginx/conf.d/recycle.conf
cp "$DIR/recycle.so4.kr" /etc/nginx/sites-available/recycle.so4.kr
ln -sf /etc/nginx/sites-available/recycle.so4.kr /etc/nginx/sites-enabled/recycle.so4.kr

if ! nginx -t; then
    echo "설정 오류: 이전 파일로 되돌립니다" >&2
    for f in recycle.conf recycle.so4.kr; do
        b="/tmp/$f.bak.$STAMP"
        if [ -f "$b" ]; then
            case $f in recycle.conf) cp "$b" /etc/nginx/conf.d/recycle.conf ;; *) cp "$b" /etc/nginx/sites-available/recycle.so4.kr ;; esac
        elif [ "$f" = recycle.conf ]; then
            rm -f /etc/nginx/conf.d/recycle.conf
        fi
    done
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
echo "recycle_access.log 마지막 줄 (좌표가 없어야 정상):"
tail -n 1 /var/log/nginx/recycle_access.log 2>/dev/null || echo "(아직 기록 없음)"
if grep -q "lat=" /var/log/nginx/recycle_access.log 2>/dev/null; then
    echo "경고: 로그에 좌표가 남았습니다" >&2
fi
echo "완료: https://recycle.so4.kr"
