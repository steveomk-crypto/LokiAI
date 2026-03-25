#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKDIR="${ROOT}"
LOG_FILE="${WORKDIR}/system_logs/telegram_summary.log"
PID_FILE="${WORKDIR}/system_logs/telegram_summary.pid"
RUNNER="${WORKDIR}/scripts/run_telegram_summary_cycle.sh"
SLEEP_SECONDS=900

mkdir -p "$(dirname "${LOG_FILE}")"

if [ -f "${PID_FILE}" ]; then
  existing_pid="$(cat "${PID_FILE}")"
  if kill -0 "${existing_pid}" 2>/dev/null; then
    echo "$(date -Iseconds) - telegram summary daemon already running as PID ${existing_pid}" >&2
    exit 1
  else
    echo "$(date -Iseconds) - removing stale telegram summary PID file for ${existing_pid}" >&2
    rm -f "${PID_FILE}"
  fi
fi

echo $$ > "${PID_FILE}"
trap 'rm -f "${PID_FILE}"' EXIT

exec >> "${LOG_FILE}"
exec 2>&1

echo "$(date -Iseconds) - telegram summary daemon started (PID $$)"

while true; do
  echo "$(date -Iseconds) - invoking run_telegram_summary_cycle.sh"
  bash "${RUNNER}"
  echo "$(date -Iseconds) - telegram summary finished, sleeping ${SLEEP_SECONDS}s"
  sleep "${SLEEP_SECONDS}"
done
