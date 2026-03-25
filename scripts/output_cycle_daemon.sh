#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKDIR="${ROOT}"
LOG_FILE="${WORKDIR}/system_logs/output_cycle.log"
PID_FILE="${WORKDIR}/system_logs/output_cycle.pid"
RUNNER="${WORKDIR}/scripts/run_output_cycle.sh"
SLEEP_SECONDS=300

mkdir -p "$(dirname "${LOG_FILE}")"

if [ -f "${PID_FILE}" ]; then
  existing_pid="$(cat "${PID_FILE}")"
  if kill -0 "${existing_pid}" 2>/dev/null; then
    echo "$(date -Iseconds) - output cycle daemon already running as PID ${existing_pid}" >&2
    exit 1
  else
    echo "$(date -Iseconds) - removing stale output daemon PID file for ${existing_pid}" >&2
    rm -f "${PID_FILE}"
  fi
fi

echo $$ > "${PID_FILE}"
trap 'rm -f "${PID_FILE}"' EXIT

exec >> "${LOG_FILE}"
exec 2>&1

echo "$(date -Iseconds) - output cycle daemon started (PID $$)"

while true; do
  echo "$(date -Iseconds) - invoking run_output_cycle.sh"
  bash "${RUNNER}"
  echo "$(date -Iseconds) - output cycle finished, sleeping ${SLEEP_SECONDS}s"
  sleep "${SLEEP_SECONDS}"
done
