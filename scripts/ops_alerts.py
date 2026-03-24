#!/usr/bin/env python3
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib import parse, request

from scripts.telegram_lanes import resolve_lane_target
from zoneinfo import ZoneInfo

WORKSPACE = Path('/home/lokiai/.openclaw/workspace')
CACHE = WORKSPACE / 'cache'
SYSTEM_LOGS = WORKSPACE / 'system_logs'
PAPER_TRADES = WORKSPACE / 'paper_trades'
SECRETS = WORKSPACE / 'secrets'

MARKET_STATE_PATH = CACHE / 'market_state.json'
WS_STATE_PATH = CACHE / 'coinbase_ws_state.json'
TRADER_AUDIT_PATH = PAPER_TRADES / 'paper_trader_v2_audit_summary.json'
OPS_STATE_PATH = CACHE / 'ops_alerts_state.json'
TELEGRAM_ENV_PATH = SECRETS / 'telegram_bot.env'

OPS_CHAT_ID = '-1003837497443'
OPS_THREAD_ID = '5'
LOCAL_TZ = ZoneInfo('America/Los_Angeles')
SCANNER_STALE_MINUTES = 20
WS_STALE_MINUTES = 10
SERVICE_EXPECTATIONS = {
    'Coinbase Websocket': {'pid_path': SYSTEM_LOGS / 'coinbase_ws.pid', 'match': 'feeds/coinbase_ws.py'},
    'Operator Dashboard': {'port': 8500, 'match': 'dashboard.operator_main'},
    'Stream Dashboard': {'port': 8501, 'match': 'dashboard.stream_main'},
}


def load_env_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip().removeprefix('export ').strip()
        data[key] = value.strip().strip('"').strip("'")
    return data


def load_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def save_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_ts(value: str | None):
    if not value:
        return None
    for fmt in ('%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M%z', '%Y-%m-%dT%H:%M'):
        try:
            dt = datetime.strptime(value, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=LOCAL_TZ)
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def age_minutes(ts: str | None):
    dt = parse_ts(ts)
    if dt is None:
        return None
    return (now_utc() - dt).total_seconds() / 60


def pid_running(pid_path: Path) -> bool:
    if not pid_path.exists():
        return False
    try:
        pid = int(pid_path.read_text().strip())
    except Exception:
        return False
    return Path(f'/proc/{pid}').exists()


def command_has_match(match: str) -> bool:
    try:
        out = subprocess.check_output(['ps', '-ef'], text=True)
    except Exception:
        return False
    return any(match in line and 'ops_alerts.py' not in line for line in out.splitlines())


def port_listening(port: int) -> bool:
    try:
        out = subprocess.check_output(['ss', '-ltnp'], text=True)
    except Exception:
        return False
    needle = f':{port} '
    return needle in out or f':{port}\n' in out


def send_telegram(token: str, text: str) -> tuple[bool, str]:
    lane_chat_id, lane_thread_id = resolve_lane_target('ops')
    payload_dict = {
        'chat_id': lane_chat_id or OPS_CHAT_ID,
        'text': text,
    }
    thread_id = lane_thread_id or OPS_THREAD_ID
    if thread_id:
        payload_dict['message_thread_id'] = thread_id
    payload = parse.urlencode(payload_dict).encode()
    req = request.Request(f'https://api.telegram.org/bot{token}/sendMessage', data=payload)
    try:
        with request.urlopen(req, timeout=20) as resp:
            return True, resp.read().decode('utf-8', errors='replace')
    except Exception as exc:
        return False, str(exc)


def scanner_status() -> tuple[str, str]:
    market_state = load_json(MARKET_STATE_PATH)
    if market_state is None:
        return 'error', 'Scanner state missing: market_state.json unavailable.'
    age = age_minutes(market_state.get('computed_at'))
    if age is None:
        return 'error', 'Scanner failure: computed_at missing or malformed.'
    if age > SCANNER_STALE_MINUTES:
        return 'stale', f'Scanner stale: no fresh update in {age:.1f}m.'
    return 'running', f'Scanner healthy: fresh update {age:.1f}m ago.'


def websocket_status() -> tuple[str, str]:
    ws_state = load_json(WS_STATE_PATH)
    if ws_state is None:
        return 'error', 'Coinbase Websocket state missing.'
    if not ws_state.get('connected'):
        return 'offline', 'Coinbase Websocket offline.'
    age = age_minutes(ws_state.get('last_message_at'))
    if age is None:
        return 'error', 'Coinbase Websocket failure: last_message_at missing or malformed.'
    if age > WS_STALE_MINUTES:
        return 'stale', f'Coinbase Websocket stale: no live message in {age:.1f}m.'
    reconnect_count = ws_state.get('reconnect_count', 0)
    if reconnect_count and reconnect_count >= 3:
        return 'reconnecting', f'Coinbase Websocket reconnecting repeatedly: {reconnect_count} reconnects.'
    return 'online', f'Coinbase Websocket healthy: fresh message {age:.1f}m ago.'


def trader_status(previous: dict) -> tuple[str, str, str | None]:
    audit = load_json(TRADER_AUDIT_PATH)
    if audit is None:
        return 'error', 'Paper Trader V2 audit missing.', None
    mode = audit.get('mode', 'watch')
    slots = audit.get('active_slot_count', 0)
    latest_closed = (audit.get('latest_closed') or [{}])[0]
    close_sig = None
    if latest_closed and latest_closed.get('exit_time'):
        close_sig = f"{latest_closed.get('token')}|{latest_closed.get('exit_reason')}|{latest_closed.get('exit_time')}"
    if mode == 'engaged':
        return 'engaged', f'Paper Trader V2 engaged: {slots} active slot(s).', close_sig
    return 'watch', 'Paper Trader V2 in watch mode.', close_sig


def service_statuses() -> dict[str, tuple[str, str]]:
    results: dict[str, tuple[str, str]] = {}
    for service, spec in SERVICE_EXPECTATIONS.items():
        healthy = False
        if spec.get('port'):
            healthy = port_listening(spec['port'])
        elif spec.get('pid_path'):
            healthy = pid_running(spec['pid_path'])

        if healthy and spec.get('match'):
            healthy = command_has_match(spec['match'])

        if healthy:
            results[service] = ('online', f'{service} online.')
        else:
            results[service] = ('offline', f'{service} offline unexpectedly.')
    return results


def maybe_enqueue(alerts: list[str], prev_state: str | None, curr_state: str, text: str, noisy_ok: set[str] | None = None):
    noisy_ok = noisy_ok or set()
    if curr_state != prev_state and (curr_state in noisy_ok or curr_state in {'stale', 'error', 'offline', 'reconnecting'}):
        alerts.append(text)
    elif prev_state in {'stale', 'error', 'offline', 'reconnecting'} and curr_state in {'running', 'online', 'watch', 'engaged'}:
        alerts.append(text)


def main() -> int:
    env = load_env_file(TELEGRAM_ENV_PATH)
    token = env.get('TELEGRAM_BOT_TOKEN') or os.environ.get('TELEGRAM_BOT_TOKEN')
    if not token:
        print('telegram token missing')
        return 1

    previous = load_json(OPS_STATE_PATH) or {}
    alerts: list[str] = []
    next_state: dict = {'checked_at': now_utc().isoformat(), 'subsystems': {}, 'last_close_sig': previous.get('last_close_sig')}

    scanner_state, scanner_text = scanner_status()
    maybe_enqueue(alerts, previous.get('subsystems', {}).get('scanner', {}).get('state'), scanner_state, f'[scanner][{scanner_state}] {scanner_text}')
    next_state['subsystems']['scanner'] = {'state': scanner_state, 'detail': scanner_text}

    ws_state, ws_text = websocket_status()
    maybe_enqueue(alerts, previous.get('subsystems', {}).get('websocket', {}).get('state'), ws_state, f'[websocket][{ws_state}] {ws_text}')
    next_state['subsystems']['websocket'] = {'state': ws_state, 'detail': ws_text}

    trader_state, trader_text, close_sig = trader_status(previous)
    prev_trader_state = previous.get('subsystems', {}).get('trader', {}).get('state')
    if trader_state != prev_trader_state:
        alerts.append(f'[trader][{trader_state}] {trader_text}')
    prev_close_sig = previous.get('last_close_sig')
    if close_sig and close_sig != prev_close_sig:
        audit = load_json(TRADER_AUDIT_PATH) or {}
        latest_closed = (audit.get('latest_closed') or [{}])[0]
        token_name = latest_closed.get('token', '?')
        reason = latest_closed.get('exit_reason', 'unknown')
        pnl = latest_closed.get('pnl_percent', 0)
        alerts.append(f'[trader][close] Paper Trader V2 close: {token_name} • {reason} • {pnl:+.3f}%.')
        next_state['last_close_sig'] = close_sig
    next_state['subsystems']['trader'] = {'state': trader_state, 'detail': trader_text}

    services = service_statuses()
    next_state['subsystems']['services'] = {}
    for service, (state, text) in services.items():
        prev_service_state = previous.get('subsystems', {}).get('services', {}).get(service, {}).get('state')
        maybe_enqueue(alerts, prev_service_state, state, f'[service][{state}] {text}')
        next_state['subsystems']['services'][service] = {'state': state, 'detail': text}

    deliveries = []
    for text in alerts:
        ok, result = send_telegram(token, text)
        deliveries.append({'text': text, 'ok': ok, 'result': result})

    next_state['deliveries'] = deliveries[-20:]
    save_json(OPS_STATE_PATH, next_state)
    print(json.dumps(next_state, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
