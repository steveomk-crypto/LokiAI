from __future__ import annotations

import json
from pathlib import Path
from typing import Any

WORKSPACE = Path('/home/lokiai/.openclaw/workspace')
MODES_PATH = WORKSPACE / 'ops_state' / 'dashboard_modes.json'

DEFAULT_MODES = {
    'market_broadcaster': True,
    'telegram_sender': False,
    'x_autoposter': False,
    'performance_analyzer': True,
    'sol_shadow_logger': True,
}


def _load_json(path: Path, default: Any):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(payload, indent=2))
    tmp.replace(path)


def get_modes() -> dict[str, bool]:
    modes = _load_json(MODES_PATH, {})
    if not isinstance(modes, dict):
        modes = {}
    merged = dict(DEFAULT_MODES)
    for key, value in modes.items():
        merged[key] = bool(value)
    return merged


def set_mode(component_id: str, enabled: bool) -> dict[str, bool]:
    modes = get_modes()
    modes[component_id] = bool(enabled)
    _write_json(MODES_PATH, modes)
    return modes
