from __future__ import annotations

import json
from pathlib import Path
from typing import Any

WORKSPACE = Path('/home/lokiai/.openclaw/workspace')
STATE_PATH = WORKSPACE / 'config' / 'x_state.json'
QUEUE_DIR = WORKSPACE / 'x_posts' / 'queue'
DRAFT_DIR = WORKSPACE / 'x_posts' / 'drafts'
POST_LOG = WORKSPACE / 'x_posts' / 'post_log.json'
RUNTIME_LOG = WORKSPACE / 'system_logs' / 'x_autoposter.log'

DEFAULT_STATE = {
    'mode': 'draft_only',
    'allowedAutoClasses': ['market_radar', 'build_in_public'],
    'lastDraftAt': None,
    'lastPostAt': None,
    'lastResult': None,
}


def _read_json(path: Path, default: Any):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    tmp.replace(path)


def ensure_x_layout() -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    DRAFT_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME_LOG.parent.mkdir(parents=True, exist_ok=True)
    if not STATE_PATH.exists():
        _write_json(STATE_PATH, DEFAULT_STATE)
    if not POST_LOG.exists():
        _write_json(POST_LOG, [])


def get_x_state() -> dict[str, Any]:
    ensure_x_layout()
    payload = _read_json(STATE_PATH, {})
    if not isinstance(payload, dict):
        payload = {}
    merged = dict(DEFAULT_STATE)
    merged.update(payload)
    return merged


def save_x_state(state: dict[str, Any]) -> None:
    ensure_x_layout()
    _write_json(STATE_PATH, state)
