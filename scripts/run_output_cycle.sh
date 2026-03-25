#!/bin/bash
set -euo pipefail

LOCK_FILE="/tmp/output_cycle.lock"
exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  echo "$(date -Iseconds) - output cycle already running; exiting." >&2
  exit 0
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

for task in market_broadcaster telegram_sender performance_analyzer sol_paper_trader; do
  echo "$(date -Iseconds) - Running ${task}"
  python3 autonomous_market_loop.py --task "${task}"
  echo "$(date -Iseconds) - Completed ${task}"
done

echo "$(date -Iseconds) - Running solana shadow logger"
python3 scripts/log_sol_shadow_fills.py || true
echo "$(date -Iseconds) - Completed solana shadow logger"

echo "$(date -Iseconds) - Output cycle complete"
