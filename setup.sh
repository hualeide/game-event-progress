#!/usr/bin/env bash
# 活动进度 — Linux/macOS 一键设置
set -euo pipefail
cd "$(dirname "$0")"

echo "==> 检查 Python…"
if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "未找到 python3，请先安装 Python 3.10+" >&2
  exit 1
fi

echo "==> 创建数据目录…"
mkdir -p data public/data

if [[ -f requirements.txt ]]; then
  echo "==> 安装依赖（如有）…"
  "$PY" -m pip install -r requirements.txt || true
fi

echo "==> 发布已有数据到 public/data…"
"$PY" scripts/publish_data.py

chmod +x docker-entrypoint.sh scripts/run_update.sh 2>/dev/null || true

cat <<EOF

完成。下一步：
  抓取更新:  $PY scripts/update.py
  本地预览:  $PY -m http.server 5173
             打开 http://localhost:5173/public/
  Docker:    docker compose up -d  → http://localhost:8080
  API 服务:  $PY scripts/server.py  → http://localhost:8080
EOF
