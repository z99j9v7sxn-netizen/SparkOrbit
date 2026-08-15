#!/usr/bin/env bash
set -euo pipefail
echo "=== mount ==="
sudo docker exec sparkorbit-frontend ls /materials
echo "=== nginx location ==="
sudo docker exec sparkorbit-frontend sh -c 'grep -A8 materials /etc/nginx/conf.d/default.conf'
echo "=== headers small pdf ==="
URLPATH=$(python3 -c 'import urllib.parse; print(urllib.parse.quote("数据结构(c语言版)复习知识点.pdf"))')
curl -skSI "https://wikj.online/static/materials/${URLPATH}" | tr -d '\r' | grep -iE 'HTTP/|Accept-Ranges|Cache-Control|Content-Length|Content-Type|Server'
echo "=== range 206 ==="
curl -skS -o /dev/null -D - -H 'Range: bytes=0-1023' "https://wikj.online/static/materials/${URLPATH}" | tr -d '\r' | grep -iE 'HTTP/|Content-Range|Accept-Ranges|Content-Length'
echo "=== linearize log tail ==="
tail -30 /tmp/linearize_materials.log || true
ps aux | grep -E 'linearize|qpdf' | grep -v grep || echo 'linearize_idle'
