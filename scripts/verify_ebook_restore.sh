#!/usr/bin/env bash
set -uo pipefail
U=$(python3 -c 'import urllib.parse; print(urllib.parse.quote("考研复习指导书/2027数据结构_高清带书签版.pdf"))')
URL="https://wikj.online/static/materials/${U}"
echo "=== sizes ==="
ls -lhS /opt/sparkorbit/资料/考研复习指导书/
echo "=== range ==="
curl -skS -o /dev/null -D - -H 'Range: bytes=0-65535' "$URL" | tr -d '\r' | grep -iE 'HTTP/|Content-Range|Accept-Ranges|Cache-Control|Content-Length'
echo "=== linearized ==="
qpdf --show-linearization "/opt/sparkorbit/资料/考研复习指导书/2027数据结构_高清带书签版.pdf" 2>&1 | head -12
echo "=== frontend up ==="
sudo docker compose -f /opt/sparkorbit/docker-compose.yml ps frontend --format '{{.Status}}'
