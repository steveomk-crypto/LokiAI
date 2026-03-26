#!/usr/bin/env bash
set -euo pipefail

WORKSPACE="/home/lokiai/.openclaw/workspace"
LOG_DIR="$WORKSPACE/system_logs"
PID_FILE="$LOG_DIR/position_reflex.pid"
OUT_FILE="$LOG_DIR/position_reflex.log"
INTERVAL_SECONDS="${POSITION_REFLEX_INTERVAL_SECONDS:-5}"

mkdir -p "$LOG_DIR"
echo $$ > "$PID_FILE"
trap 'rm -f "$PID_FILE"' EXIT

cd "$WORKSPACE"

echo "[$(date -Is)] position_reflex loop starting (interval=${INTERVAL_SECONDS}s)" >> "$OUT_FILE"
while true; do
  python3 autonomous_market_loop.py --task position_reflex >> "$OUT_FILE" 2>&1 || true
  sleep "$INTERVAL_SECONDS"
done
