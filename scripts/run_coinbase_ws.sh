#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p system_logs cache market_logs/coinbase_ws

LOG="system_logs/coinbase_ws.log"
PID="system_logs/coinbase_ws.pid"

PYTHONPATH="$ROOT" nohup python3 feeds/coinbase_ws.py >> "$LOG" 2>&1 &
echo $! > "$PID"

echo "Started Coinbase websocket service: PID $(cat "$PID")"
echo "Log: $LOG"
