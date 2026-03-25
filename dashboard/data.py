import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo
import signal

import requests
import os

from dashboard.runtime_registry import COMPONENTS
from dashboard.modes import get_modes
from scripts.x_state import get_x_state
from scripts.telegram_lanes import load_telegram_lanes

WORKDIR = Path('/home/lokiai/.openclaw/workspace')
CACHE_DIR = WORKDIR / 'cache'
MARKET_LOG_DIR = WORKDIR / 'market_logs'
COINBASE_WS_LOG_DIR = MARKET_LOG_DIR / 'coinbase_ws'
SYSTEM_LOG_DIR = WORKDIR / 'system_logs'
PID_DIR = SYSTEM_LOG_DIR

MARKET_STATE_PATH = CACHE_DIR / 'market_state.json'
COINBASE_WS_STATE_PATH = CACHE_DIR / 'coinbase_ws_state.json'
COINBASE_PRODUCTS_PATH = CACHE_DIR / 'coinbase_products.json'
COINBASE_TICKERS_PATH = CACHE_DIR / 'coinbase_tickers.json'
BTC_CANDLES_CACHE_PATH = CACHE_DIR / 'btc_usd_candles_1m.json'
OPEN_POSITIONS_PATH = WORKDIR / 'paper_trades' / 'open_positions.json'
OPEN_POSITIONS_V2_PATH = WORKDIR / 'paper_trades' / 'open_positions_v2.json'
PAPER_TRADER_V2_AUDIT_PATH = WORKDIR / 'paper_trades' / 'paper_trader_v2_audit_summary.json'
SOCIAL_INTEL_PULSE_PATH = CACHE_DIR / 'social_intel_pulse.json'
LOCAL_TZ = ZoneInfo('America/Los_Angeles')


def _load_json(path: Path, default: Any):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _safe_iso_to_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    formatted = value[:-1] + '+00:00' if value.endswith('Z') else value
    try:
        dt = datetime.fromisoformat(formatted)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=LOCAL_TZ)
    return dt.astimezone(timezone.utc)


def _iso_now() -> datetime:
    return datetime.now(timezone.utc)


def _file_meta(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {'exists': False, 'path': str(path), 'updated_at': None, 'size_bytes': None}
    stat = path.stat()
    updated_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
    return {'exists': True, 'path': str(path), 'updated_at': updated_at, 'size_bytes': stat.st_size}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open('r', encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _atomic_json_write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(payload, indent=2))
    tmp.replace(path)


def load_market_state() -> dict[str, Any]:
    return _load_json(MARKET_STATE_PATH, {})


def load_coinbase_ws_state() -> dict[str, Any]:
    return _load_json(COINBASE_WS_STATE_PATH, {})


def load_coinbase_products() -> list[dict[str, Any]]:
    return _load_json(COINBASE_PRODUCTS_PATH, [])


def load_coinbase_tickers() -> dict[str, dict[str, Any]]:
    return _load_json(COINBASE_TICKERS_PATH, {})


def load_product_candles(product_id: str, limit: int = 48, granularity: int = 60) -> dict[str, Any]:
    safe_name = product_id.lower().replace('-', '_')
    granularity_label = f'{int(granularity // 60)}m' if granularity % 60 == 0 else f'{granularity}s'
    cache_path = CACHE_DIR / f'{safe_name}_candles_{granularity_label}.json'
    url = f'https://api.exchange.coinbase.com/products/{product_id}/candles?granularity={granularity}'
    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        rows = response.json()
        candles = []
        for row in sorted(rows, key=lambda x: x[0])[-limit:]:
            ts, low, high, open_, close, volume = row
            candles.append(
                {
                    'time': datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
                    'open': open_,
                    'high': high,
                    'low': low,
                    'close': close,
                    'volume': volume,
                }
            )
        payload = {'pair': product_id, 'granularity': granularity, 'candles': candles}
        _atomic_json_write(cache_path, payload)
        return payload
    except Exception:
        return _load_json(cache_path, {'pair': product_id, 'granularity': granularity, 'candles': []})


def load_btc_candles(limit: int = 48) -> dict[str, Any]:
    return load_product_candles('BTC-USD', limit=limit, granularity=60)


def load_open_positions() -> list[dict[str, Any]]:
    return _load_json(OPEN_POSITIONS_PATH, [])


def load_open_positions_v2() -> list[dict[str, Any]]:
    return _load_json(OPEN_POSITIONS_V2_PATH, [])


def load_paper_trader_v2_audit() -> dict[str, Any]:
    return _load_json(PAPER_TRADER_V2_AUDIT_PATH, {})


def load_social_intel_pulse() -> dict[str, Any]:
    return _load_json(SOCIAL_INTEL_PULSE_PATH, {'updated_at': None, 'items': []})


def load_latest_market_log_entries(limit: int = 500) -> list[dict[str, Any]]:
    path = MARKET_LOG_DIR / f'{datetime.now().date().isoformat()}.jsonl'
    rows = _read_jsonl(path)
    return rows[-limit:]


def load_coinbase_ws_snapshots(limit: int = 200) -> list[dict[str, Any]]:
    path = COINBASE_WS_LOG_DIR / f'{datetime.now().date().isoformat()}.jsonl'
    rows = _read_jsonl(path)
    return rows[-limit:]


def build_scanner_run_history(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in entries:
        ts = row.get('timestamp')
        if ts:
            grouped[ts].append(row)

    history = []
    for ts, rows in sorted(grouped.items()):
        top_score = max((float(r.get('score') or 0.0) for r in rows), default=0.0)
        high_quality = sum(1 for r in rows if float(r.get('score') or 0.0) >= 0.30)
        history.append(
            {
                'timestamp': ts,
                'signal_count': len(rows),
                'top_score': round(top_score, 6),
                'high_quality_count': high_quality,
            }
        )
    return history[-20:]


def build_persistence_summary(entries: list[dict[str, Any]], min_repeats: int = 2) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in entries:
        token = row.get('token')
        if token:
            grouped[token].append(row)

    summary = []
    for token, rows in grouped.items():
        if len(rows) < min_repeats:
            continue
        latest = rows[-1]
        summary.append(
            {
                'token': token,
                'repeat_count': len(rows),
                'latest_persistence': latest.get('persistence', 0),
                'latest_score': float(latest.get('score') or 0.0),
                'latest_trend': latest.get('momentum_trend', '–'),
                'latest_momentum': float(latest.get('momentum') or 0.0),
            }
        )
    summary.sort(key=lambda x: (x['repeat_count'], x['latest_score']), reverse=True)
    return summary[:15]


def build_coinbase_live_movers(tickers: dict[str, dict[str, Any]], limit: int = 15) -> list[dict[str, Any]]:
    rows = [row for row in tickers.values() if row.get('price') is not None]
    rows.sort(key=lambda x: abs(float(x.get('drift_300s') or 0.0)), reverse=True)
    return rows[:limit]


def build_focus_leads(market_state: dict[str, Any], products: list[dict[str, Any]], tickers: dict[str, dict[str, Any]], scanner_entries: list[dict[str, Any]] | None = None, limit: int = 3) -> list[dict[str, Any]]:
    top_opps = market_state.get('top_opportunities', []) or []
    valid_products = {str(row.get('product_id') or row.get('id') or '').upper() for row in products if row.get('product_id') or row.get('id')}
    leads: list[dict[str, Any]] = []
    seen: set[str] = set()
    scanner_entries = scanner_entries or []

    def add_lead(raw: dict[str, Any], source: str) -> bool:
        token = str(raw.get('token') or raw.get('base_currency') or '').upper().strip()
        if not token:
            return False
        product_id = str(raw.get('product_id') or f'{token}-USD').upper()
        if valid_products and product_id not in valid_products:
            return False
        if product_id in seen:
            return False

        ticker = tickers.get(product_id, {}) if isinstance(tickers, dict) else {}
        lead = dict(raw)
        lead['token'] = token
        lead['product_id'] = product_id
        lead['ticker'] = ticker
        lead['candles'] = load_product_candles(product_id, limit=24, granularity=60).get('candles', [])
        lead['freshness_seconds'] = ticker.get('freshness_seconds', raw.get('freshness_seconds'))
        lead['drift_300s'] = ticker.get('drift_300s', raw.get('drift_300s'))
        lead['volume'] = raw.get('volume', ticker.get('volume_24h'))
        lead['trend'] = raw.get('trend', raw.get('momentum_trend', 'steady'))
        lead['status'] = raw.get('status', source)
        lead['source'] = source
        leads.append(lead)
        seen.add(product_id)
        return True

    for opp in top_opps:
        if add_lead(opp, 'scanner') and len(leads) >= limit:
            return leads

    live_candidates = [
        row for row in (tickers.values() if isinstance(tickers, dict) else [])
        if row.get('price') is not None and row.get('freshness_seconds') is not None and float(row.get('freshness_seconds') or 10**9) <= 180
    ]
    live_candidates.sort(
        key=lambda row: (
            abs(float(row.get('drift_300s') or 0.0)),
            float(row.get('volume_24h') or 0.0),
            -float(row.get('freshness_seconds') or 10**9),
        ),
        reverse=True,
    )
    for row in live_candidates:
        candidate = {
            'token': row.get('base_currency'),
            'product_id': row.get('product_id'),
            'score': abs(float(row.get('drift_300s') or 0.0)),
            'momentum': float(row.get('drift_900s') or row.get('drift_300s') or 0.0),
            'persistence': 1,
            'status': 'live mover',
            'trend': 'accelerating' if float(row.get('drift_300s') or 0.0) > 0 else 'fading' if float(row.get('drift_300s') or 0.0) < 0 else 'steady',
            'volume': row.get('volume_24h'),
            'freshness_seconds': row.get('freshness_seconds'),
            'drift_300s': row.get('drift_300s'),
        }
        if add_lead(candidate, 'live_mover') and len(leads) >= limit:
            return leads

    latest_by_token: dict[str, dict[str, Any]] = {}
    for row in scanner_entries:
        token = str(row.get('token') or '').upper().strip()
        if not token or not row.get('coinbase_actionable', True):
            continue
        previous = latest_by_token.get(token)
        if not previous or str(row.get('timestamp') or '') >= str(previous.get('timestamp') or ''):
            latest_by_token[token] = row

    persistence_candidates = sorted(
        latest_by_token.values(),
        key=lambda row: (
            float(row.get('persistence') or 0.0),
            float(row.get('score') or 0.0),
            float(row.get('momentum') or 0.0),
        ),
        reverse=True,
    )
    for row in persistence_candidates:
        if add_lead(row, 'persistence') and len(leads) >= limit:
            return leads

    return leads


def build_coinbase_universe_health(products: list[dict[str, Any]], tickers: dict[str, dict[str, Any]], ws_state: dict[str, Any]) -> dict[str, Any]:
    ticker_rows = list(tickers.values())
    active = sum(1 for row in ticker_rows if row.get('price') is not None)
    stale = sum(1 for row in ticker_rows if (row.get('freshness_seconds') or 10**9) > 300)
    freshest = sorted(
        [row for row in ticker_rows if row.get('freshness_seconds') is not None],
        key=lambda x: x.get('freshness_seconds', 10**9),
    )[:5]
    return {
        'tracked_products': len(products),
        'active_products': active,
        'stale_products': stale,
        'reconnect_count': ws_state.get('reconnect_count', 0),
        'freshest_symbols': freshest,
    }


def build_main_loop_status(log_path: Path) -> dict[str, Any]:
    info: dict[str, Any] = {
        'daemon_started_at': None,
        'last_cycle_started_at': None,
        'last_cycle_completed_at': None,
        'last_task': None,
        'last_task_completed': None,
        'last_error': None,
        'task_started_at': {},
        'task_completed_at': {},
    }
    if not log_path.exists():
        return info
    try:
        lines = log_path.read_text(encoding='utf-8', errors='ignore').splitlines()[-800:]
    except Exception:
        return info

    cycle_start_idx = 0
    for idx, line in enumerate(lines):
        text = line.strip()
        if 'market cycle daemon started' in text:
            info['daemon_started_at'] = text[:25]
        if 'invoking run_market_cycle.sh' in text:
            info['last_cycle_started_at'] = text[:25]
            cycle_start_idx = idx

    cycle_lines = lines[cycle_start_idx:] if lines else []
    for line in cycle_lines:
        text = line.strip()
        if 'Market cycle complete' in text:
            info['last_cycle_completed_at'] = text[:25]
        if 'Running ' in text:
            task_name = text.split('Running ', 1)[1].strip()
            info['last_task'] = task_name
            info['task_started_at'][task_name] = text[:25]
        if 'Completed ' in text:
            task_name = text.split('Completed ', 1)[1].strip()
            info['last_task_completed'] = task_name
            info['task_completed_at'][task_name] = text[:25]
        if 'Traceback' in text or 'Permission denied' in text or 'FileNotFoundError' in text:
            info['last_error'] = text
    return info


def build_status_flags(market_state: dict[str, Any], ws_state: dict[str, Any]) -> list[dict[str, str]]:
    flags = []
    market_dt = _safe_iso_to_dt(market_state.get('computed_at'))
    ws_dt = _safe_iso_to_dt(ws_state.get('last_message_at'))
    now = datetime.now(timezone.utc)

    if market_dt and market_dt.tzinfo is None:
        market_dt = market_dt.replace(tzinfo=timezone.utc)
    if ws_dt and ws_dt.tzinfo is None:
        ws_dt = ws_dt.replace(tzinfo=timezone.utc)

    if not market_dt:
        flags.append({'level': 'warning', 'message': 'Scanner state missing'})
    else:
        scanner_age = (datetime.now(timezone.utc).timestamp() - market_dt.timestamp())
        if scanner_age > 3600:
            flags.append({'level': 'warning', 'message': 'Scanner data stale'})

    if not ws_state:
        flags.append({'level': 'warning', 'message': 'Websocket state missing'})
    elif not ws_state.get('connected'):
        flags.append({'level': 'danger', 'message': 'Coinbase websocket disconnected'})
    elif not ws_dt:
        flags.append({'level': 'warning', 'message': 'Coinbase websocket data stale'})
    else:
        ws_age = (datetime.now(timezone.utc).timestamp() - ws_dt.timestamp())
        if ws_age > 300:
            flags.append({'level': 'warning', 'message': 'Coinbase websocket data stale'})

    return flags


def _pid_value(pid_path: Path) -> int | None:
    try:
        return int(pid_path.read_text().strip())
    except Exception:
        return None


def _pid_running(pid_path: Path) -> bool:
    pid = _pid_value(pid_path)
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _runtime_entry(label: str, pid_path: Path | None, state_running: str = 'running', state_stopped: str = 'stopped', log_path: Path | None = None, available: bool | None = None, transient: bool = False) -> dict[str, Any]:
    running = _pid_running(pid_path) if pid_path else bool(available)
    pid = _pid_value(pid_path) if pid_path else None
    log_meta = _file_meta(log_path) if log_path else None
    state = state_running if running else state_stopped
    if not running and log_meta and log_meta.get('updated_at'):
        state = f'{state} (recent activity)'
    entry = {
        'label': label,
        'running': running,
        'state': state,
        'pid_file': str(pid_path) if pid_path else None,
        'pid': pid,
        'log_file': str(log_path) if log_path else None,
        'log_meta': log_meta,
        'transient': transient,
    }
    return entry


def _is_recent(updated_at: str | None, threshold_seconds: int) -> bool:
    dt = _safe_iso_to_dt(updated_at)
    if not dt:
        return False
    return (datetime.now(timezone.utc) - dt).total_seconds() <= threshold_seconds


def _canonical_display_state(entry: dict[str, Any]) -> str:
    state = str(entry.get('state') or '').lower()
    desired = str(entry.get('desired_state') or '').lower()
    if any(term in state for term in ('running', 'data healthy')) or bool(entry.get('running')):
        return 'RUNNING'
    if entry.get('last_error') and 'blocked by dependencies' not in str(entry.get('last_error')).lower():
        return 'FAILED'
    if any(term in state for term in ('active recently', 'recently completed', 'available')):
        return 'ACTIVE'
    if state == 'managed by main loop':
        return 'ACTIVE'
    if desired in {'enabled', 'disabled'}:
        return state.upper() if state else desired.upper()
    if entry.get('dependency_health') == 'blocked':
        return 'WAITING' if entry.get('owned_by') == 'automation' else 'BLOCKED'
    if 'degraded' in state or 'stale' in state:
        return 'DEGRADED'
    return 'IDLE'


def _apply_component_health_overrides(runtime: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ws_state = load_coinbase_ws_state()
    market_state = load_market_state()
    loop_info = build_main_loop_status(SYSTEM_LOG_DIR / 'market_loop_cron.log') if 'main_loop' in runtime else {}
    x_state = get_x_state() if 'x_autoposter' in runtime else {}
    telegram_lanes = load_telegram_lanes() if 'telegram_sender' in runtime else {}

    main_loop_engaged = False
    if 'main_loop' in runtime:
        main_loop_engaged = bool(runtime['main_loop'].get('running')) or _is_recent((runtime['main_loop'].get('log_meta') or {}).get('updated_at'), 120)

    if 'coinbase_feed' in runtime and ws_state.get('connected') and _is_recent(ws_state.get('last_message_at'), 300):
        runtime['coinbase_feed']['running'] = True
        runtime['coinbase_feed']['state'] = 'running (data healthy)'
        runtime['coinbase_feed']['last_success_at'] = ws_state.get('last_message_at')
    if 'market_scanner' in runtime and market_state.get('computed_at') and _is_recent(market_state.get('computed_at'), 300):
        runtime['market_scanner']['state'] = 'recently completed'
        runtime['market_scanner']['last_success_at'] = market_state.get('computed_at')
    if 'main_loop' in runtime and _is_recent((runtime['main_loop'].get('log_meta') or {}).get('updated_at'), 120):
        runtime['main_loop']['state'] = 'active recently'
    if 'main_loop' in runtime and loop_info.get('last_error'):
        runtime['main_loop']['last_error'] = loop_info.get('last_error')
    automation_stage_map = {
        'market_scanner': 'market_scanner',
        'paper_trader_v2': 'paper_trader',
        'position_manager': 'position_manager',
    }
    for component_id, task_name in automation_stage_map.items():
        completed_at = loop_info.get('task_completed_at', {}).get(task_name)
        if component_id in runtime and completed_at and _is_recent(completed_at, 90):
            runtime[component_id]['state'] = 'recently completed'
            runtime[component_id]['last_success_at'] = completed_at

    if main_loop_engaged:
        if 'market_scanner' in runtime and not runtime['market_scanner'].get('last_success_at'):
            runtime['market_scanner']['state'] = 'managed by main loop'
        if 'paper_trader_v2' in runtime and str(runtime['paper_trader_v2'].get('last_error') or '').lower().startswith('blocked by dependencies'):
            runtime['paper_trader_v2']['state'] = 'managed by main loop'
            runtime['paper_trader_v2']['last_error'] = None
        if 'position_manager' in runtime and not runtime['position_manager'].get('last_success_at'):
            runtime['position_manager']['state'] = 'managed by main loop'

    if 'x_autoposter' in runtime:
        runtime['x_autoposter']['state'] = str(x_state.get('mode') or 'draft_only')
        runtime['x_autoposter']['last_success_at'] = x_state.get('lastPostAt') or x_state.get('lastDraftAt')
        runtime['x_autoposter']['last_result'] = x_state.get('lastResult')
    if 'telegram_sender' in runtime:
        lane_count = len((telegram_lanes.get('lanes') or {})) if isinstance(telegram_lanes, dict) else 0
        runtime['telegram_sender']['state'] = f'{lane_count} lanes configured' if lane_count else 'lanes missing'
        runtime['telegram_sender']['last_result'] = f'{lane_count} lanes ready' if lane_count else 'lane config missing'

    return loop_info


def _apply_dependency_health(runtime: dict[str, dict[str, Any]]) -> None:
    for comp_id, entry in runtime.items():
        deps = entry.get('dependencies') or []
        if not deps:
            entry['dependency_health'] = 'clear'
            entry['dependency_blockers'] = []
        else:
            blockers = []
            for dep in deps:
                dep_entry = runtime.get(dep)
                dep_state = str((dep_entry or {}).get('state') or '').lower()
                dep_running = bool((dep_entry or {}).get('running'))
                if not dep_entry:
                    blockers.append(dep)
                elif dep_running:
                    continue
                elif any(term in dep_state for term in ('running', 'recently completed', 'active recently', 'data healthy', 'available')):
                    continue
                else:
                    blockers.append(dep)
            entry['dependency_health'] = 'blocked' if blockers else 'clear'
            entry['dependency_blockers'] = blockers

        entry['controls_blocked'] = entry['dependency_health'] == 'blocked' and entry.get('kind') in {'service', 'job'}
        entry['blocked_reason'] = ', '.join(entry.get('dependency_blockers') or []) if entry['controls_blocked'] else None
        desired_state = str(entry.get('desired_state') or 'unknown')
        if desired_state == 'on':
            entry['desired_state_ok'] = bool(entry.get('running')) or any(term in str(entry.get('state') or '').lower() for term in ('running', 'active recently', 'data healthy'))
        elif desired_state == 'auto':
            entry['desired_state_ok'] = entry.get('dependency_health') == 'clear'
        elif desired_state == 'enabled':
            entry['desired_state_ok'] = entry.get('dependency_health') == 'clear'
        elif desired_state == 'disabled':
            entry['desired_state_ok'] = True
        else:
            entry['desired_state_ok'] = True
        if entry.get('dependency_health') == 'blocked' and not entry.get('last_error'):
            entry['last_error'] = f"Blocked by dependencies: {entry['blocked_reason']}"
        entry['display_state'] = _canonical_display_state(entry)


def read_runtime_controls() -> dict[str, dict[str, Any]]:
    runtime: dict[str, dict[str, Any]] = {}
    mode_overrides = get_modes()
    for comp_id, comp in COMPONENTS.items():
        available = None
        if comp_id == 'performance_analyzer':
            out = comp.outputs[0] if comp.outputs else None
            available = any(out.glob('*')) if out and out.exists() and out.is_dir() else bool(out and out.exists())
        entry = _runtime_entry(
            comp.name,
            comp.pid_file,
            log_path=comp.log_path,
            state_running='running',
            state_stopped='idle' if comp.kind == 'job' else 'stopped',
            available=available,
            transient=(comp.kind == 'job'),
        )
        entry['component_id'] = comp.id
        entry['category'] = comp.category
        entry['kind'] = comp.kind
        entry['dependencies'] = comp.dependencies
        entry['owned_by'] = 'automation' if comp.id in {'coinbase_feed', 'market_scanner', 'paper_trader_v2', 'position_manager', 'main_loop'} else 'manual'
        entry['notes'] = comp.notes
        entry['start_script'] = comp.start_script
        entry['inspect_target'] = str(comp.inspect_target) if comp.inspect_target else None
        entry['start_label'] = comp.start_label
        if comp_id in mode_overrides:
            entry['desired_state'] = 'enabled' if mode_overrides[comp_id] else 'disabled'
        else:
            entry['desired_state'] = comp.desired_default or ('on' if comp.kind == 'service' else 'auto' if comp.kind == 'job' else 'unknown')
        entry['desired_state_ok'] = True
        entry['last_success_at'] = (entry.get('log_meta') or {}).get('updated_at')
        entry['last_error'] = None
        runtime[comp_id] = entry

    _apply_component_health_overrides(runtime)
    _apply_dependency_health(runtime)
    return runtime


def build_controls_placeholder(market_state: dict[str, Any], ws_state: dict[str, Any], open_positions_v2: list[dict[str, Any]], audit_v2: dict[str, Any]) -> list[dict[str, Any]]:
    runtime = read_runtime_controls()
    return [
        {'group': comp_id, **entry}
        for comp_id, entry in runtime.items()
    ]


def compute_dashboard_state() -> dict[str, Any]:
    market_state = load_market_state()
    ws_state = load_coinbase_ws_state()
    products = load_coinbase_products()
    tickers = load_coinbase_tickers()
    scanner_entries = load_latest_market_log_entries()
    ws_snapshots = load_coinbase_ws_snapshots()
    btc_candles = load_btc_candles()
    open_positions = load_open_positions()
    open_positions_v2 = load_open_positions_v2()
    paper_trader_v2_audit = load_paper_trader_v2_audit()
    social_intel_pulse = load_social_intel_pulse()

    return {
        'market_state': market_state,
        'ws_state': ws_state,
        'products': products,
        'tickers': tickers,
        'scanner_entries': scanner_entries,
        'ws_snapshots': ws_snapshots,
        'btc_candles': btc_candles,
        'open_positions': open_positions,
        'open_positions_v2': open_positions_v2,
        'paper_trader_v2_audit': paper_trader_v2_audit,
        'social_intel_pulse': social_intel_pulse,
        'scanner_history': build_scanner_run_history(scanner_entries),
        'persistence_summary': build_persistence_summary(scanner_entries),
        'live_movers': build_coinbase_live_movers(tickers),
        'focus_leads': build_focus_leads(market_state, products, tickers, scanner_entries=scanner_entries),
        'universe_health': build_coinbase_universe_health(products, tickers, ws_state),
        'main_loop_status': build_main_loop_status(SYSTEM_LOG_DIR / 'market_loop_cron.log'),
        'status_flags': build_status_flags(market_state, ws_state),
        'controls_placeholder': build_controls_placeholder(market_state, ws_state, open_positions_v2, paper_trader_v2_audit),
        'meta': {
            'market_state': _file_meta(MARKET_STATE_PATH),
            'coinbase_ws_state': _file_meta(COINBASE_WS_STATE_PATH),
            'coinbase_products': _file_meta(COINBASE_PRODUCTS_PATH),
            'coinbase_tickers': _file_meta(COINBASE_TICKERS_PATH),
        },
    }
