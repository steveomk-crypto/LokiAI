#!/bin/bash
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKDIR="${ROOT}"
LOG="$WORKDIR/system_logs/manual_loop_$(date -u +%Y%m%dT%H%M%SZ).log"
END_TIME=$(($(date +%s) + 7200))  # two hours
CYCLE=1

run_task() {
  local task="$1"
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] START $task" | tee -a "$LOG"
  (cd "$WORKDIR" && python3 autonomous_market_loop.py --task "$task" >> "$LOG" 2>&1)
  local status=$?
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] END $task (exit $status)" | tee -a "$LOG"
}

run_flatten() {
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] START paper_trader_flatten" | tee -a "$LOG"
  (cd "$WORKDIR" && PAPER_TRADER_FLATTEN=1 python3 autonomous_market_loop.py --task paper_trader >> "$LOG" 2>&1)
  local status=$?
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] END paper_trader_flatten (exit $status)" | tee -a "$LOG"
}

while [ $(date +%s) -lt $END_TIME ]; do
  echo "=== Cycle ${CYCLE} @ $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee -a "$LOG"
  run_task market_scanner
  sleep 5
  run_task paper_trader
  sleep 5
  run_task position_manager
  sleep 5
  run_task sol_paper_trader
  sleep 5
  run_task market_broadcaster
  sleep 5
  run_task telegram_sender
  sleep 5
  run_task performance_analyzer
  CYCLE=$((CYCLE + 1))
  if [ $(date +%s) -lt $END_TIME ]; then
    sleep 30
  fi
done

run_flatten

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] SESSION SUMMARY" | tee -a "$LOG"
(cd "$WORKDIR" && python3 scripts/session_wrap_summary.py >> "$LOG" 2>&1)

echo "Manual loop completed at $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$LOG"
