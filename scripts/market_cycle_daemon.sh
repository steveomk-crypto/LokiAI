#!/bin/bash
set -euo pipefail

WORKDIR="/data/.openclaw/workspace"
LOG_FILE="${WORKDIR}/system_logs/market_loop_cron.log"
PID_FILE="${WORKDIR}/system_logs/market_cycle_daemon.pid"
RUNNER="${WORKDIR}/scripts/run_market_cycle.sh"
SLEEP_SECONDS=60

mkdir -p "$(dirname "${LOG_FILE}")"

if [ -f "${PID_FILE}" ]; then
  existing_pid="$(cat "${PID_FILE}")"
  if kill -0 "${existing_pid}" 2>/dev/null; then
    echo "$(date -Iseconds) - market cycle daemon already running as PID ${existing_pid}" >&2
    exit 1
  fi
fi

echo $$ > "${PID_FILE}"
trap 'rm -f "${PID_FILE}"' EXIT

exec >> "${LOG_FILE}"
exec 2>&1

echo "$(date -Iseconds) - market cycle daemon started (PID $$)"

while true; do
  echo "$(date -Iseconds) - invoking run_market_cycle.sh"
  bash "${RUNNER}"
  echo "$(date -Iseconds) - cycle finished, sleeping ${SLEEP_SECONDS}s"
  sleep "${SLEEP_SECONDS}"
done
