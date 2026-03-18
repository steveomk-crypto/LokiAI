#!/usr/bin/env bash
set -euo pipefail

cd /data/.openclaw/workspace
export PYTHONPATH="/data/.openclaw/workspace:${PYTHONPATH:-}"
PORT_VALUE="${DASHBOARD_PORT:-8500}"
HOST_VALUE="${DASHBOARD_HOST:-0.0.0.0}"

export DASHBOARD_HOST="${HOST_VALUE}"
export DASHBOARD_PORT="${PORT_VALUE}"
exec python3 -m dashboard.main
