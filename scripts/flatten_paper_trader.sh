#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p system_logs
LOG="system_logs/paper_trader_flatten.log"
PID="system_logs/paper_trader_flatten.pid"

PYTHONPATH="$ROOT" nohup bash -lc 'python3 scripts/flatten_paper_trader_v2.py >> system_logs/paper_trader_flatten.log 2>&1' >> "$LOG" 2>&1 &
echo $! > "$PID"

echo "Started paper trader flatten: PID $(cat "$PID")"
echo "Log: $LOG"
