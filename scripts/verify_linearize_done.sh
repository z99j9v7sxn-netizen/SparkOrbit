#!/usr/bin/env bash
set -euo pipefail
echo "=== failed retry sample ==="
f='/opt/sparkorbit/资料/课本/高等数学第8版上册.pdf'
qpdf --linearize "$f" "$f.retry" 2>&1 | tail -8 || true
rm -f "$f.retry"
echo "=== check linearized flags ==="
for f in \
  '/opt/sparkorbit/资料/考研复习指导书/2027数据结构_高清带书签版.pdf' \
  '/opt/sparkorbit/资料/考研复习指导书/王道2027操作系统-高清带书签.pdf'
do
  info=$(qpdf --json --json-key=linearized "$f" 2>/dev/null | tr -d '\n' || true)
  echo "$f => $info"
done
echo "=== HTTP range large pdf ==="
U=$(python3 -c 'import urllib.parse; print(urllib.parse.quote("考研复习指导书/2027数据结构_高清带书签版.pdf"))')
curl -skS -o /dev/null -D - -H 'Range: bytes=0-524287' "https://wikj.online/static/materials/${U}" | tr -d '\r' | grep -iE 'HTTP/|Content-Range|Accept-Ranges|Cache-Control|Content-Length'
# cleanup temps
find /opt/sparkorbit/资料 -name '*.lin.*' -o -name '*.retry' 2>/dev/null | while read -r x; do rm -f "$x"; done
echo DONE
