#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p system_logs
LOG="system_logs/paper_trader_v2.log"
PID="system_logs/paper_trader_v2.pid"

if [ -f "$PID" ]; then
  existing_pid="$(cat "$PID" 2>/dev/null || true)"
  if [ -n "$existing_pid" ] && ps -p "$existing_pid" -o args= 2>/dev/null | grep -q 'paper_trader_v2.py'; then
    echo "Paper trader v2 already running: PID $existing_pid"
    echo "Log: $LOG"
    exit 0
  fi
  rm -f "$PID"
fi

PYTHONPATH="$ROOT" nohup python3 skills/paper-trader/paper_trader_v2.py >> "$LOG" 2>&1 &
echo $! > "$PID"

echo "Started paper trader v2: PID $(cat "$PID")"
echo "Log: $LOG"
