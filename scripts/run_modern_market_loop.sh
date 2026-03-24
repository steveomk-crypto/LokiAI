#!/usr/bin/env bash
set -euo pipefail

LOCK_FILE="/tmp/modern_market_loop.lock"
exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  echo "$(date -Iseconds) - modern market loop already running; exiting." >&2
  exit 0
fi

WORKDIR="/home/lokiai/.openclaw/workspace"
LOG="$WORKDIR/system_logs/modern_market_loop.log"

cd "$WORKDIR"
export PYTHONPATH="$WORKDIR"

echo "[$(date -Iseconds)] START modern market loop" >> "$LOG"

echo "[$(date -Iseconds)] scanner" >> "$LOG"
python3 skills/market_scanner/market_scanner.py >> "$LOG" 2>&1

echo "[$(date -Iseconds)] social_intel_pulse" >> "$LOG"
python3 scripts/build_social_intel_pulse.py >> "$LOG" 2>&1

echo "[$(date -Iseconds)] paper_trader_v2" >> "$LOG"
python3 skills/paper-trader/paper_trader_v2.py >> "$LOG" 2>&1

echo "[$(date -Iseconds)] ops_alerts" >> "$LOG"
python3 scripts/ops_alerts.py >> "$LOG" 2>&1

echo "[$(date -Iseconds)] END modern market loop" >> "$LOG"
