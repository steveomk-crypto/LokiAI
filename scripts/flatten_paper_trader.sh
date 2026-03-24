#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p system_logs
LOG="system_logs/paper_trader_flatten.log"
PID="system_logs/paper_trader_flatten.pid"

PYTHONPATH="$ROOT" nohup bash -lc 'PAPER_TRADER_FLATTEN=1 python3 autonomous_market_loop.py --task paper_trader >> system_logs/paper_trader_flatten.log 2>&1' >> "$LOG" 2>&1 &
echo $! > "$PID"

echo "Started paper trader flatten: PID $(cat "$PID")"
echo "Log: $LOG"
