#!/bin/bash
set -euo pipefail

LOCK_FILE="/tmp/core_cycle.lock"
exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  echo "$(date -Iseconds) - core cycle already running; exiting." >&2
  exit 0
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "$(date -Iseconds) - Starting core cycle"
python3 autonomous_market_loop.py --lint

echo "$(date -Iseconds) - Running pre-cycle validation"
if ! python3 scripts/pre_cycle_validation.py; then
  echo "$(date -Iseconds) - Pre-cycle validation failed; aborting core cycle"
  exit 1
fi

for task in market_scanner paper_trader position_manager; do
  echo "$(date -Iseconds) - Running ${task}"
  python3 autonomous_market_loop.py --task "${task}"
  echo "$(date -Iseconds) - Completed ${task}"
done

echo "$(date -Iseconds) - Core cycle complete"
