#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p system_logs trade_journal performance_reports
LOG="system_logs/log_trading_outputs.log"
PID="system_logs/log_trading_outputs.pid"

PYTHONPATH="$ROOT" nohup bash -lc '
python3 skills/trade-journal/trade_journal.py >> system_logs/log_trading_outputs.log 2>&1
python3 skills/performance-analyzer/performance_analyzer.py >> system_logs/log_trading_outputs.log 2>&1
python3 scripts/session_wrap_summary.py >> system_logs/log_trading_outputs.log 2>&1
' >> "$LOG" 2>&1 &
echo $! > "$PID"

echo "Started trading output logging: PID $(cat "$PID")"
echo "Log: $LOG"
