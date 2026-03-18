import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

WORKDIR = Path('/data/.openclaw/workspace')
PACKET_DIR = WORKDIR / 'queues' / 'market_radar'
OPEN_POSITION_CANDIDATES = [
    WORKDIR / 'paper_trades' / 'open_positions.json',
    WORKDIR / 'sol_paper_trades' / 'open_positions.json',
]
TRADES_LOG_CANDIDATES = [
    WORKDIR / 'paper_trades' / 'trades_log.json',
    WORKDIR / 'sol_paper_trades' / 'trades_log.json',
]
ENTRY_EVENTS_CANDIDATES = [
    WORKDIR / 'paper_trades' / 'entry_events.jsonl',
]
SYSTEM_LOG_DIR = WORKDIR / 'system_logs'
RUN_STATE_PATH = WORKDIR / 'run_state.json'


def _load_json(path: Path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _select_latest_path(candidates: List[Path]) -> Optional[Path]:
    existing = [path for path in candidates if path.exists()]
    if not existing:
        return None
    return max(existing, key=lambda p: p.stat().st_mtime)


def _path_meta(path: Optional[Path]) -> Tuple[Optional[str], Optional[str]]:
    if not path:
        return None, None
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return str(path), mtime.isoformat()


def load_run_baseline() -> Tuple[Optional[str], Optional[datetime]]:
    if not RUN_STATE_PATH.exists():
        return None, None
    try:
        payload = json.loads(RUN_STATE_PATH.read_text())
    except json.JSONDecodeError:
        return None, None
    baseline = payload.get('run_id')
    if not baseline:
        return None, None
    value = baseline
    if value.endswith('Z'):
        value = value[:-1] + '+00:00'
    try:
        dt_obj = datetime.fromisoformat(value)
    except ValueError:
        return baseline, None
    return baseline, dt_obj


def load_latest_packet() -> Dict:
    packets = sorted(PACKET_DIR.glob('packet_*.json'))
    if not packets:
        return {}
    return _load_json(packets[-1], {})


def load_open_positions() -> Tuple[List[Dict], Optional[str], Optional[str]]:
    path = _select_latest_path(OPEN_POSITION_CANDIDATES)
    if not path:
        return [], None, None
    data = _load_json(path, [])
    path_str, iso_mtime = _path_meta(path)
    return data, path_str, iso_mtime


def load_trades() -> Tuple[List[Dict], Optional[str], Optional[str]]:
    path = _select_latest_path(TRADES_LOG_CANDIDATES)
    if not path:
        return [], None, None
    trades = _load_json(path, [])
    path_str, iso_mtime = _path_meta(path)
    return trades, path_str, iso_mtime


def load_entry_events(limit: int = 10) -> Tuple[List[Dict], Optional[str], Optional[str]]:
    events: List[Dict] = []
    path = _select_latest_path(ENTRY_EVENTS_CANDIDATES)
    if not path or not path.exists():
        return events, None, None
    with path.open('r') as handle:
        for line in handle.readlines()[-limit:]:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    path_str, iso_mtime = _path_meta(path)
    return list(reversed(events)), path_str, iso_mtime


def load_loop_status() -> Dict:
    logs = sorted(SYSTEM_LOG_DIR.glob('manual_loop_*.log'))
    if not logs:
        return {'status': 'idle', 'last_cycle': '–'}
    latest = logs[-1]
    tail = latest.read_text().splitlines()[-40:]
    last_cycle = next((line for line in reversed(tail) if line.startswith('=== Cycle')), None)
    completed = any('Manual loop completed' in line for line in tail)
    status = 'idle' if completed else 'running'
    if last_cycle and '@' in last_cycle:
        last_cycle_time = last_cycle.split('@', 1)[1].split('===')[0].strip()
    else:
        last_cycle_time = '–'
    return {
        'status': status,
        'last_cycle': last_cycle_time,
        'log': latest.name,
    }
