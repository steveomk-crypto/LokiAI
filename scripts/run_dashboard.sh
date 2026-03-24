#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p system_logs
LOG="system_logs/dashboard_ui.log"
PID="system_logs/dashboard_ui.pid"

export PYTHONPATH="$ROOT:${PYTHONPATH:-}"
PORT_VALUE="${DASHBOARD_PORT:-8500}"
HOST_VALUE="${DASHBOARD_HOST:-0.0.0.0}"

export DASHBOARD_HOST="${HOST_VALUE}"
export DASHBOARD_PORT="${PORT_VALUE}"

nohup python3 -m dashboard.main >> "$LOG" 2>&1 &
echo $! > "$PID"

echo "Started operator dashboard: PID $(cat "$PID")"
echo "Log: $LOG"
