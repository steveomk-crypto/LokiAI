#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "$(date -Iseconds) - Running telegram_sender summary cycle"
python3 autonomous_market_loop.py --task telegram_sender
