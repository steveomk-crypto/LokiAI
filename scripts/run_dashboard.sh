#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export PYTHONPATH="$ROOT:${PYTHONPATH:-}"
PORT_VALUE="${DASHBOARD_PORT:-8500}"
HOST_VALUE="${DASHBOARD_HOST:-0.0.0.0}"

export DASHBOARD_HOST="${HOST_VALUE}"
export DASHBOARD_PORT="${PORT_VALUE}"
exec python3 -m dashboard.main
