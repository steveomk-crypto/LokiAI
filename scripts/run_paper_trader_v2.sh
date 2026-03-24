#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p system_logs
LOG="system_logs/paper_trader_v2.log"
PID="system_logs/paper_trader_v2.pid"

PYTHONPATH="$ROOT" nohup python3 skills/paper-trader/paper_trader_v2.py >> "$LOG" 2>&1 &
echo $! > "$PID"

echo "Started paper trader v2: PID $(cat "$PID")"
echo "Log: $LOG"
