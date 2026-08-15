#!/usr/bin/env bash
set -uo pipefail
PDF='考研复习指导书/2027数据结构_高清带书签版.pdf'
U=$(python3 -c 'import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))' "$PDF")
URL="https://wikj.online/static/materials/${U}"
FILE="/opt/sparkorbit/资料/${PDF}"

echo "=== file ==="
ls -lh "$FILE"
qpdf --show-linearization "$FILE" 2>&1 | head -15 || true

echo "=== local loopback range 512k ==="
curl -skS -o /dev/null -w 'ttfb=%{time_starttransfer} total=%{time_total} size=%{size_download} code=%{http_code}\n' \
  --resolve wikj.online:443:127.0.0.1 -H 'Range: bytes=0-524287' "$URL"

echo "=== public range 512k ==="
curl -skS -o /dev/null -w 'ttfb=%{time_starttransfer} total=%{time_total} size=%{size_download} code=%{http_code}\n' \
  -H 'Range: bytes=0-524287' "$URL"

echo "=== public full 5MB timed ==="
curl -skS -o /dev/null -w 'ttfb=%{time_starttransfer} total=%{time_total} size=%{size_download} speed=%{speed_download}\n' \
  -H 'Range: bytes=0-5242879' "$URL"

echo "=== nginx vs backend (materials should be nginx) ==="
curl -skSI "$URL" | tr -d '\r' | grep -iE 'HTTP/|Server|Cache-Control|Accept-Ranges|Content-Length'

echo "=== which books in DB sample ==="
cd /opt/sparkorbit && sudo docker compose exec -T mysql mysql -uroot -psparkorbit -N -e \
  "SELECT title, LEFT(file_url,120), page_count FROM sparkorbit.star_assets WHERE asset_type IN ('book','pdf','problem_doc') LIMIT 8;" 2>/dev/null || true
