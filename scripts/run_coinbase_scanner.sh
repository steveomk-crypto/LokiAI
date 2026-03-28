#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p system_logs
LOG="system_logs/run_coinbase_scanner.log"
PID="system_logs/coinbase_scanner.pid"

if [ -f "$PID" ]; then
  existing_pid="$(cat "$PID" 2>/dev/null || true)"
  if [ -n "$existing_pid" ] && ps -p "$existing_pid" -o args= 2>/dev/null | grep -q 'run_coinbase_scanner.sh\|market_scanner.py'; then
    echo "Scanner already running: PID $existing_pid"
    echo "Log: $LOG"
    exit 0
  fi
  rm -f "$PID"
fi

PYTHONPATH="$ROOT" nohup bash -lc 'python3 skills/market_scanner/market_scanner.py >> system_logs/run_coinbase_scanner.log 2>&1; python3 scripts/build_social_intel_pulse.py >> system_logs/run_coinbase_scanner.log 2>&1' >> "$LOG" 2>&1 &
echo $! > "$PID"

echo "Started scanner: PID $(cat "$PID")"
echo "Log: $LOG"
