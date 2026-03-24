#!/usr/bin/env bash
set -euo pipefail

cd /home/lokiai/.openclaw/workspace
export PYTHONPATH="$(pwd)"
python3 skills/market_scanner/market_scanner.py >> system_logs/run_coinbase_scanner.log 2>&1
python3 scripts/build_social_intel_pulse.py >> system_logs/run_coinbase_scanner.log 2>&1
