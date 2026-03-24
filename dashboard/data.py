import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo
import signal

import requests

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
BTC_CANDLES_CACHE_PATH = CACHE_DIR / 'btc_usd_candles_5m.json'
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


def load_product_candles(product_id: str, limit: int = 48) -> dict[str, Any]:
    safe_name = product_id.lower().replace('-', '_')
    cache_path = CACHE_DIR / f'{safe_name}_candles_5m.json'
    url = f'https://api.exchange.coinbase.com/products/{product_id}/candles?granularity=300'
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
        payload = {'pair': product_id, 'granularity': 300, 'candles': candles}
        _atomic_json_write(cache_path, payload)
        return payload
    except Exception:
        return _load_json(cache_path, {'pair': product_id, 'granularity': 300, 'candles': []})


def load_btc_candles(limit: int = 48) -> dict[str, Any]:
    return load_product_candles('BTC-USD', limit=limit)


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
    }
    if not log_path.exists():
        return info
    try:
        lines = log_path.read_text(encoding='utf-8', errors='ignore').splitlines()[-400:]
    except Exception:
        return info

    for line in lines:
        text = line.strip()
        if 'market cycle daemon started' in text:
            info['daemon_started_at'] = text[:25]
        if 'invoking run_market_cycle.sh' in text:
            info['last_cycle_started_at'] = text[:25]
        if 'Market cycle complete' in text:
            info['last_cycle_completed_at'] = text[:25]
        if 'Running ' in text:
            info['last_task'] = text.split('Running ', 1)[1].strip()
        if 'Completed ' in text:
            info['last_task_completed'] = text.split('Completed ', 1)[1].strip()
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


def read_runtime_controls() -> dict[str, dict[str, str | bool | None]]:
    scanner_pid = PID_DIR / 'coinbase_scanner.pid'
    websocket_pid = PID_DIR / 'coinbase_ws.pid'
    dashboard_pid = PID_DIR / 'dashboard_ui.pid'
    stream_pid = PID_DIR / 'stream_dashboard_ui.pid'

    scanner_running = _pid_running(scanner_pid)
    websocket_running = _pid_running(websocket_pid)
    dashboard_running = _pid_running(dashboard_pid)
    stream_running = _pid_running(stream_pid)

    paper_trader_pid = PID_DIR / 'paper_trader_v2.pid'
    loop_pid = PID_DIR / 'market_cycle_daemon.pid'
    scanner_log = PID_DIR / 'run_coinbase_scanner.log'
    websocket_log = PID_DIR / 'coinbase_ws.log'
    trader_log = PID_DIR / 'paper_trader_v2.log'
    operator_log = PID_DIR / 'dashboard_ui.log'
    stream_log = PID_DIR / 'stream_dashboard_ui.log'
    loop_log = PID_DIR / 'market_loop_cron.log'
    flatten_pid = PID_DIR / 'paper_trader_flatten.pid'
    flatten_log = PID_DIR / 'paper_trader_flatten.log'
    log_outputs_pid = PID_DIR / 'log_trading_outputs.pid'
    log_outputs_log = PID_DIR / 'log_trading_outputs.log'
    reports_ready = any((WORKDIR / 'performance_reports').glob('*')) if (WORKDIR / 'performance_reports').exists() else False

    return {
        'scanner': _runtime_entry('Scanner Engine', scanner_pid, log_path=scanner_log, state_running='running', state_stopped='idle', transient=True),
        'websocket': _runtime_entry('Coinbase Feed', websocket_pid, log_path=websocket_log),
        'paper_trader_v2': _runtime_entry('Paper Trader V2', paper_trader_pid, log_path=trader_log),
        'flatten': _runtime_entry('Flatten Paper Trades', flatten_pid, log_path=flatten_log, state_running='running', state_stopped='idle', transient=True),
        'operator': _runtime_entry('Operator Dashboard', dashboard_pid, log_path=operator_log),
        'stream': _runtime_entry('Stream Dashboard', stream_pid, log_path=stream_log),
        'loop': _runtime_entry('Main Loop Daemon', loop_pid, log_path=loop_log),
        'log_outputs': _runtime_entry('Log Trading Outputs', log_outputs_pid, log_path=log_outputs_log, state_running='running', state_stopped='idle', transient=True),
        'reports': _runtime_entry('Reports Folder', None, state_running='available', state_stopped='empty', available=reports_ready),
    }


def build_controls_placeholder(market_state: dict[str, Any], ws_state: dict[str, Any], open_positions_v2: list[dict[str, Any]], audit_v2: dict[str, Any]) -> list[dict[str, Any]]:
    runtime = read_runtime_controls()
    return [
        {'group': 'scanner', **runtime['scanner']},
        {'group': 'websocket', **runtime['websocket']},
        {'group': 'paper_trader_v2', **runtime['paper_trader_v2']},
        {'group': 'flatten', **runtime['flatten']},
        {'group': 'operator', **runtime['operator']},
        {'group': 'stream', **runtime['stream']},
        {'group': 'loop', **runtime['loop']},
        {'group': 'log_outputs', **runtime['log_outputs']},
        {'group': 'reports', **runtime['reports']},
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
