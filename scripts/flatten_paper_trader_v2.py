#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path('/home/lokiai/.openclaw/workspace')
TRADES_DIR = WORKSPACE / 'paper_trades'
OPEN_PATH = TRADES_DIR / 'open_positions_v2.json'
LOG_PATH = TRADES_DIR / 'trades_log_v2.json'
STATE_PATH = TRADES_DIR / 'paper_trader_v2_state.json'
AUDIT_PATH = TRADES_DIR / 'paper_trader_v2_audit_summary.json'
FUNNEL_PATH = TRADES_DIR / 'v2_entry_funnel_report.json'
SNAPSHOT_DIR = TRADES_DIR / 'snapshots'


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
    tmp.write_text(json.dumps(payload, indent=2) + '\n')
    tmp.replace(path)


def _now_dt() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _now_iso() -> str:
    return _now_dt().isoformat()


def _snapshot_current_files(stamp: str) -> None:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    for path in [OPEN_PATH, LOG_PATH, STATE_PATH, AUDIT_PATH, FUNNEL_PATH]:
        if path.exists():
            shutil.copy2(path, SNAPSHOT_DIR / f'{stamp}_flatten_reset_{path.name}')


def main() -> None:
    open_positions = _load_json(OPEN_PATH, [])
    now = _now_iso()
    stamp = _now_dt().strftime('%Y%m%dT%H%M%SZ')

    _snapshot_current_files(stamp)

    flattened_positions = []
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
        flattened_positions.append(closed)

    state = {
        'session_reset_at': now,
        'symbol_state': {},
        'last_run_at': None,
        'last_scan_timestamp': None,
        'last_candidates': [],
        'last_rejections': [],
        'last_entries': {},
        'notes': 'flatten_v2 full reset requested by user',
    }
    audit = {
        'timestamp': now,
        'mode': 'watch',
        'active_slot_count': 0,
        'closed_trade_count': 0,
        'win_count': 0,
        'loss_count': 0,
        'avg_win_pct': 0.0,
        'avg_loss_pct': 0.0,
        'latest_closed': [],
        'latest_open': [],
        'last_manual_flatten_at': now,
    }
    funnel = {
        'generated_at': now,
        'scanner': {'runs': 0, 'nonzero_signal_runs': 0, 'zero_signal_runs': 0, 'top_surfaced_tokens': {}},
        'trader': {'runs': 0, 'watch_runs': 0, 'engaged_runs': 0, 'shortlist_nonzero_runs': 0, 'shortlist_zero_runs': 0, 'new_positions_total': 0, 'closed_positions_total': 0},
        'candidate_flow': {'eval_count': 0, 'accepted_count': 0, 'rejected_count': 0, 'top_reject_reasons': {}},
        'dominant_tokens': [],
        'latest_audit': audit,
        'session_reset_at': now,
    }

    _write_json(LOG_PATH, [])
    _write_json(OPEN_PATH, [])
    _write_json(STATE_PATH, state)
    _write_json(AUDIT_PATH, audit)
    _write_json(FUNNEL_PATH, funnel)

    print(json.dumps({
        'timestamp': now,
        'flattened_count': len(flattened_positions),
        'reset': True,
        'session_reset_at': now,
        'open_positions_path': str(OPEN_PATH),
        'trades_log_path': str(LOG_PATH),
        'state_path': str(STATE_PATH),
        'audit_summary_path': str(AUDIT_PATH),
        'funnel_report_path': str(FUNNEL_PATH),
    }, indent=2))


if __name__ == '__main__':
    main()
