#!/usr/bin/env sh
set -eu

cd /app
mkdir -p data public/data

INTERVAL_H="${UPDATE_INTERVAL_HOURS:-6}"
case "$INTERVAL_H" in
  ''|*[!0-9]*) INTERVAL_H=6 ;;
esac
INTERVAL_S=$((INTERVAL_H * 3600))
if [ "$INTERVAL_S" -lt 300 ]; then INTERVAL_S=300; fi

# 后台定时抓取（首次启动也跑一轮，失败不阻断服务）
(
  sleep 5
  while true; do
    echo "[entrypoint] running scripts/update.py …"
    python scripts/update.py --jobs 1 --timeout 300 \
      >> data/update-cron.log 2>&1 || echo "[entrypoint] update failed (see data/update-cron.log)"
    sleep "$INTERVAL_S"
  done
) &

exec python scripts/server.py
