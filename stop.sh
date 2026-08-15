#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v docker >/dev/null 2>&1; then
  echo "[错误] 未检测到 Docker。"
  exit 1
fi

echo "[停止] docker compose down"
docker compose down
echo "已停止。如需清除数据库数据，请执行: docker compose down -v"
