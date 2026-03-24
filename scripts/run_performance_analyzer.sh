#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p system_logs performance_reports
LOG="system_logs/performance_analyzer.log"

PYTHONPATH="$ROOT" python3 skills/performance-analyzer/performance_analyzer.py >> "$LOG" 2>&1

echo "Ran performance analyzer"
echo "Log: $LOG"
