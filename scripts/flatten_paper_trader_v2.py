#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path('/home/lokiai/.openclaw/workspace')
TRADES_DIR = WORKSPACE / 'paper_trades'
OPEN_PATH = TRADES_DIR / 'open_positions_v2.json'
LOG_PATH = TRADES_DIR / 'trades_log_v2.json'
AUDIT_PATH = TRADES_DIR / 'paper_trader_v2_audit_summary.json'


def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(payload, indent=2))
    tmp.replace(path)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def main() -> None:
    open_positions = _load_json(OPEN_PATH, [])
    trades_log = _load_json(LOG_PATH, [])
    now = _now_iso()

    closed_positions = []
    for position in open_positions:
        closed = dict(position)
        closed.update({
            'status': 'closed',
            'trade_state': 'MANUAL_FLATTEN',
            'exit_reason': 'manual_flatten_v2',
            'exit_category': 'EXIT',
            'exit_time': now,
            'last_update': now,
        })
        closed_positions.append(closed)

    if closed_positions:
        trades_log.extend(closed_positions)

    audit = _load_json(AUDIT_PATH, {})
    audit.update({
        'timestamp': now,
        'mode': 'watch',
        'active_slot_count': 0,
        'closed_trade_count': len(trades_log),
        'latest_closed': trades_log[-5:],
        'latest_open': [],
        'last_manual_flatten_at': now,
    })

    _write_json(LOG_PATH, trades_log)
    _write_json(OPEN_PATH, [])
    _write_json(AUDIT_PATH, audit)

    print(json.dumps({
        'timestamp': now,
        'flattened_count': len(closed_positions),
        'open_positions_path': str(OPEN_PATH),
        'trades_log_path': str(LOG_PATH),
        'audit_summary_path': str(AUDIT_PATH),
    }, indent=2))


if __name__ == '__main__':
    main()
