#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p system_logs cache market_logs/coinbase_ws

LOG="system_logs/coinbase_ws.log"
PID="system_logs/coinbase_ws.pid"

if [ -f "$PID" ]; then
  existing_pid="$(cat "$PID" 2>/dev/null || true)"
  if [ -n "$existing_pid" ] && ps -p "$existing_pid" -o args= 2>/dev/null | grep -q 'feeds/coinbase_ws.py'; then
    echo "Coinbase websocket service already running: PID $existing_pid"
    echo "Log: $LOG"
    exit 0
  fi
  rm -f "$PID"
fi

PYTHONPATH="$ROOT" nohup python3 feeds/coinbase_ws.py >> "$LOG" 2>&1 &
echo $! > "$PID"

echo "Started Coinbase websocket service: PID $(cat "$PID")"
echo "Log: $LOG"
