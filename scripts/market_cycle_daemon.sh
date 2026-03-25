#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKDIR="${ROOT}"
LOG_FILE="${WORKDIR}/system_logs/market_loop_cron.log"
PID_FILE="${WORKDIR}/system_logs/market_cycle_daemon.pid"
RUNNER="${WORKDIR}/scripts/run_core_cycle.sh"
SLEEP_SECONDS=30

mkdir -p "$(dirname "${LOG_FILE}")"

if [ -f "${PID_FILE}" ]; then
  existing_pid="$(cat "${PID_FILE}")"
  if kill -0 "${existing_pid}" 2>/dev/null; then
    existing_cmd="$(ps -p "${existing_pid}" -o args= 2>/dev/null || true)"
    if printf '%s' "${existing_cmd}" | grep -q "market_cycle_daemon.sh"; then
      echo "$(date -Iseconds) - market cycle daemon already running as PID ${existing_pid}" >&2
      exit 1
    fi
  fi
  echo "$(date -Iseconds) - removing stale daemon PID file for ${existing_pid}" >&2
  rm -f "${PID_FILE}"
fi

echo $$ > "${PID_FILE}"
trap 'rm -f "${PID_FILE}"' EXIT INT TERM

exec >> "${LOG_FILE}"
exec 2>&1

echo "$(date -Iseconds) - market cycle daemon started (PID $$)"

while true; do
  echo "$(date -Iseconds) - invoking run_market_cycle.sh"
  bash "${RUNNER}"
  echo "$(date -Iseconds) - cycle finished, sleeping ${SLEEP_SECONDS}s"
  sleep "${SLEEP_SECONDS}"
done
