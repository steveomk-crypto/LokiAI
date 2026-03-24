from __future__ import annotations

import json
from pathlib import Path
from typing import Any

WORKSPACE = Path('/home/lokiai/.openclaw/workspace')
LANES_PATH = WORKSPACE / 'config' / 'telegram_lanes.json'


def load_telegram_lanes() -> dict[str, Any]:
    try:
        return json.loads(LANES_PATH.read_text(encoding='utf-8'))
    except Exception:
        return {'defaultMode': 'operator_channel', 'lanes': {}}


def get_lane(name: str) -> dict[str, Any]:
    payload = load_telegram_lanes()
    lanes = payload.get('lanes') or {}
    return lanes.get(name, {}) if isinstance(lanes, dict) else {}


def resolve_lane_target(name: str) -> tuple[str | None, str | None]:
    lane = get_lane(name)
    chat_id = str(lane.get('chatId') or '').strip() or None
    thread_id = str(lane.get('threadId') or '').strip() or None
    return chat_id, thread_id
