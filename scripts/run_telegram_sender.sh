#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p system_logs
LOG="system_logs/telegram_sender.log"

PYTHONPATH="$ROOT" python3 autonomous_market_loop.py --task telegram_sender >> "$LOG" 2>&1

echo "Ran telegram sender"
echo "Log: $LOG"
