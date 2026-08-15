#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v docker >/dev/null 2>&1; then
  echo "[错误] 未检测到 Docker。请先安装 Docker / Docker Desktop。"
  exit 1
fi

if [[ ! -f .env && -f .env.example ]]; then
  cp .env.example .env
  echo "[提示] 已从 .env.example 创建 .env，可按需填写 DEEPSEEK_API_KEY 等。"
fi

echo "[启动] docker compose up -d --build"
docker compose up -d --build

echo ""
echo "========================================"
echo " SparkOrbit 已启动"
echo " 浏览器打开: http://localhost"
echo " 演示账号: student001 / teacher001 / admin001"
echo " 密码: 123456"
echo "========================================"
