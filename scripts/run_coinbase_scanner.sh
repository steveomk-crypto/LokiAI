#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p system_logs
LOG="system_logs/run_coinbase_scanner.log"
PID="system_logs/coinbase_scanner.pid"

PYTHONPATH="$ROOT" nohup bash -lc 'python3 skills/market_scanner/market_scanner.py >> system_logs/run_coinbase_scanner.log 2>&1; python3 scripts/build_social_intel_pulse.py >> system_logs/run_coinbase_scanner.log 2>&1' >> "$LOG" 2>&1 &
echo $! > "$PID"

echo "Started scanner: PID $(cat "$PID")"
echo "Log: $LOG"
