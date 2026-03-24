#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p system_logs
LOG="system_logs/x_autoposter.log"

PYTHONPATH="$ROOT" python3 autonomous_market_loop.py --task x_autoposter >> "$LOG" 2>&1

echo "Ran x autoposter"
echo "Log: $LOG"
