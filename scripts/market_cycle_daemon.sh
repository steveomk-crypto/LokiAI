#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKDIR="${ROOT}"
LOG_FILE="${WORKDIR}/system_logs/market_loop_cron.log"
PID_FILE="${WORKDIR}/system_logs/market_cycle_daemon.pid"
HEARTBEAT_FILE="${WORKDIR}/system_logs/market_cycle_heartbeat.json"
RUNNER="${WORKDIR}/scripts/run_core_cycle.sh"
SLEEP_SECONDS=30

mkdir -p "$(dirname "${LOG_FILE}")"

write_heartbeat() {
  local state="$1"
  cat > "${HEARTBEAT_FILE}" <<EOF
{
  "timestamp": "$(date -Iseconds)",
  "pid": $$,
  "state": "${state}",
  "sleep_seconds": ${SLEEP_SECONDS}
}
EOF
}

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
trap 'write_heartbeat "stopping"; rm -f "${PID_FILE}"' EXIT INT TERM

exec >> "${LOG_FILE}"
exec 2>&1

echo "$(date -Iseconds) - market cycle daemon started (PID $$)"
write_heartbeat "started"

while true; do
  echo "$(date -Iseconds) - invoking run_market_cycle.sh"
  write_heartbeat "running_cycle"
  if ! bash "${RUNNER}"; then
    status=$?
    echo "$(date -Iseconds) - run_core_cycle.sh exited with status ${status}; keeping daemon alive and retrying after ${SLEEP_SECONDS}s"
    write_heartbeat "cycle_error"
    sleep "${SLEEP_SECONDS}"
    continue
  fi
  echo "$(date -Iseconds) - cycle finished, sleeping ${SLEEP_SECONDS}s"
  write_heartbeat "sleeping"
  sleep "${SLEEP_SECONDS}"
done
