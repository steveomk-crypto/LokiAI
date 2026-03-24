#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p system_logs
LOG="system_logs/market_broadcaster.log"

PYTHONPATH="$ROOT" python3 autonomous_market_loop.py --task market_broadcaster >> "$LOG" 2>&1

echo "Ran market broadcaster"
echo "Log: $LOG"
