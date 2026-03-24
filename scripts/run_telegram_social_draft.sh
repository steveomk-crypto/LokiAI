#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p system_logs
LOG="system_logs/telegram_social.log"

DRAFT_PATH=$(PYTHONPATH="$ROOT" python3 skills/telegram_queue_consumer/telegram_queue_consumer.py | python3 -c 'import json,sys; data=json.load(sys.stdin); print(data.get("draft_path") or "")')

if [ -z "$DRAFT_PATH" ] || [ ! -f "$DRAFT_PATH" ]; then
  echo "No social draft available" >> "$LOG"
  echo "No social draft available"
  exit 1
fi

TEXT=$(cat "$DRAFT_PATH")
PYTHONPATH="$ROOT" python3 scripts/send_telegram_lane_test.py social "$TEXT" >> "$LOG" 2>&1

echo "Sent Telegram social draft"
echo "Log: $LOG"
