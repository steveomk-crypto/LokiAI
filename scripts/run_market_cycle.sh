#!/bin/bash
set -euo pipefail

LOCK_FILE="/tmp/market_cycle.lock"
exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  echo "$(date -Iseconds) - market cycle already running; exiting." >&2
  exit 0
fi

WORKDIR="/data/.openclaw/workspace"
cd "${WORKDIR}"

echo "$(date -Iseconds) - Starting market cycle"
python3 autonomous_market_loop.py --lint

echo "$(date -Iseconds) - Running pre-cycle validation"
if ! python3 scripts/pre_cycle_validation.py; then
  echo "$(date -Iseconds) - Pre-cycle validation failed; aborting cycle"
  exit 1
fi

tasks=(
  market_scanner
  paper_trader
  position_manager
  market_broadcaster
  telegram_sender
  x_autoposter
  performance_analyzer
  sol_paper_trader
)

for task in "${tasks[@]}"; do
  echo "$(date -Iseconds) - Running ${task}"
  python3 autonomous_market_loop.py --task "${task}"
  echo "$(date -Iseconds) - Completed ${task}"
done

echo "$(date -Iseconds) - Running solana shadow logger"
python3 scripts/log_sol_shadow_fills.py || true
echo "$(date -Iseconds) - Completed solana shadow logger"

echo "$(date -Iseconds) - Market cycle complete"
