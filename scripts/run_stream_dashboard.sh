#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p system_logs

LOG="system_logs/stream_dashboard_ui.log"
PID="system_logs/stream_dashboard_ui.pid"

PYTHONPATH="$ROOT" DASHBOARD_HOST=0.0.0.0 DASHBOARD_PORT=8501 nohup python3 -m dashboard.stream_main >> "$LOG" 2>&1 &
echo $! > "$PID"

echo "Started stream dashboard: PID $(cat "$PID")"
echo "Log: $LOG"
