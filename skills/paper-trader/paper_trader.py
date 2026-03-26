import json
import os
from datetime import datetime, timezone, timedelta
from importlib.machinery import SourceFileLoader
from typing import Dict, List, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from api_usage import log_api_call
from atr_utils import get_atr_for_symbol

LOG_DIR = "/home/lokiai/.openclaw/workspace/market_logs"
TRADES_DIR = "/home/lokiai/.openclaw/workspace/paper_trades"
OPEN_POSITIONS_PATH = os.path.join(TRADES_DIR, "open_positions.json")
TRADES_LOG_PATH = os.path.join(TRADES_DIR, "trades_log.json")
ENTRY_STATE_PATH = os.path.join(TRADES_DIR, "entry_queue.json")
ENTRY_EVENTS_PATH = os.path.join(TRADES_DIR, "entry_events.jsonl")
SECURITY_CACHE_PATH = os.path.join(TRADES_DIR, "token_security_cache.json")
TIER_B_GUARD_STATE_PATH = os.path.join(TRADES_DIR, "tier_b_guard_state.json")
SECURITY_TTL_SECONDS = 12 * 3600
CHAIN_IDS = {
    'ethereum': '1',
    'binance-smart-chain': '56',
    'bsc': '56',
    'polygon-pos': '137',
    'arbitrum-one': '42161'
}
POSITION_SIZE_USD = 100.0
TOKEN_COOLDOWN_MINUTES = 60
TAKE_PROFIT_PCT = 8.0
STOP_LOSS_PCT = -4.0
TIER_A_POSITION_SIZE = 100.0
TIER_B_POSITION_SIZE = 20.0
TIER_B_STOP_LOSS_PCT = -3.0
TIER_B_TIME_STOP_HOURS = 0.75
TIER_B_NO_MOVE_PCT = 0.2
TIER_B_MAX_OPEN_POSITIONS = 3
TIER_B_SESSION_MAX_DRAWDOWN_USD = -12.0
LOSS_STREAK_MAX_SL = 2
LOSS_STREAK_COOLDOWN_MINUTES = 30
LOSS_STREAK_STATE_PATH = os.path.join(TRADES_DIR, "loss_streak_state.json")
TIER_B_ROTATION_MIN_SCORE = 0.55
TIER_B_ROTATION_SCORE_GAP = 0.05
TIER_B_ROTATION_MIN_DRAWDOWN = -1.5
TIER_B_ROTATION_MIN_HOLD_MINUTES = 15
TIER_A_REGIME_MIN_STRONG_SIGNALS = 1
TIER_A_REGIME_MIN_AVG_SCORE = 0.45
TIER_A_REGIME_MIN_VOLUME = 5_000_000
TIER_A_REGIME_MIN_MOMENTUM = 5.0
TIER_A_RULES = {
    'persistence': 4,
    'liquidity_score': 0.50,
    'liquidity_change_ratio': 1.0,
    'alignment': 0.30,
    'buy_pressure': -0.01
}
TIER_B_RULES = {
    'persistence': 5,
    'liquidity_score': 0.45,
    'liquidity_change_ratio': 1.0,
    'alignment': 0.2,
    'buy_pressure': -0.01
}

TIER_B_MIN_SCORE = 0.5

MARKET_STATE_PATH = '/home/lokiai/.openclaw/workspace/cache/market_state.json'
TRADE_PROFILES = {
    'baseline': {
        'tier_a_size': TIER_A_POSITION_SIZE,
        'tier_b_size': TIER_B_POSITION_SIZE,
        'tier_a_max_positions': 2,
        'tier_b_max_positions': TIER_B_MAX_OPEN_POSITIONS
    },
    'high_opportunity': {
        'tier_a_size': 120.0,
        'tier_b_size': 40.0,
        'tier_a_max_positions': 3,
        'tier_b_max_positions': TIER_B_MAX_OPEN_POSITIONS + 1
    }
}

SESSION_GUARD_MAX_DRAWDOWN_PCT = -0.06
SESSION_GUARD_HEAT_DRAWDOWN_PCT = -0.08
SESSION_GUARD_COOLDOWN_CYCLES = 3
SESSION_GUARD_PATH = '/home/lokiai/.openclaw/workspace/cache/session_guard.json'
MICROCAP_VOLUME_THRESHOLD = 50_000_000
MICROCAP_TAKE_PROFIT_PCT = 5.0
GOVERNOR_STATE_PATH = '/home/lokiai/.openclaw/workspace/cache/governor_state.json'
TOKEN_COOLDOWN_EXTRA_MINUTES = 0

COINGECKO_MARKETS_URL = (
    "https://api.coingecko.com/api/v3/coins/markets"
    "?vs_currency=usd&order=volume_desc&per_page=250&page=1&price_change_percentage=1h"
)
RISK_MANAGER_PATH = "/home/lokiai/.openclaw/workspace/skills/risk-manager/risk_manager.py"
CACHE_PATH = '/home/lokiai/.openclaw/workspace/cache/coingecko_snapshot.json'
CACHE_TTL_SECONDS = 300
RISK_MANAGER = SourceFileLoader('risk_manager', RISK_MANAGER_PATH).load_module()


def _load_latest_ranked() -> Tuple[List[Dict], str]:
    if not os.path.isdir(LOG_DIR):
        raise FileNotFoundError(f"Log directory not found: {LOG_DIR}")
    json_logs = sorted(
        [f for f in os.listdir(LOG_DIR) if f.endswith(".jsonl")],
        reverse=True
    )
    if not json_logs:
        raise FileNotFoundError("No .jsonl market logs available; run market_scanner first.")

    latest_path = os.path.join(LOG_DIR, json_logs[0])
    entries: List[Dict] = []
    with open(latest_path, 'r') as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if not entries:
        raise ValueError(f"No JSON entries found in {latest_path}")

    entries_by_ts: Dict[str, List[Dict]] = {}
    for entry in entries:
        ts = entry.get('timestamp')
        if not ts:
            continue
        entries_by_ts.setdefault(ts, []).append(entry)
    if not entries_by_ts:
        raise ValueError(f"No timestamped entries in {latest_path}")

    latest_ts = sorted(entries_by_ts.keys())[-1]
    ranked = sorted(entries_by_ts[latest_ts], key=lambda e: e.get('score', 0), reverse=True)
    return ranked[:5], latest_ts


def _fetch_market_prices_live(symbols: List[str]) -> Tuple[Dict[str, float], Dict[str, Dict]]:
    if not symbols:
        return {}, {}
    with urlopen(COINGECKO_MARKETS_URL) as resp:
        data = json.load(resp)
    log_api_call('coingecko')
    prices: Dict[str, float] = {}
    metas: Dict[str, Dict] = {}
    for item in data:
        symbol = (item.get('symbol') or '').upper()
        price = item.get('current_price')
        if not symbol or price is None:
            continue
        if symbol not in prices:
            prices[symbol] = float(price)
            metas[symbol] = {
                'id': item.get('id'),
                'name': item.get('name'),
                'symbol': symbol,
                'source': 'coingecko'
            }
    return (
        {sym: prices.get(sym) for sym in symbols if prices.get(sym) is not None},
        {sym: metas.get(sym) for sym in symbols if metas.get(sym)}
    )


def _fetch_binance_prices(symbols: List[str]) -> Tuple[Dict[str, float], Dict[str, Dict]]:
    if not symbols:
        return {}, {}
    url = "https://api.binance.com/api/v3/ticker/price"
    try:
        with urlopen(url) as resp:
            data = json.load(resp)
        log_api_call('binance')
    except (URLError, HTTPError, json.JSONDecodeError):
        return {}, {}
    wants = {sym.upper() for sym in symbols}
    prices: Dict[str, float] = {}
    metas: Dict[str, Dict] = {}
    for entry in data:
        pair = (entry.get('symbol') or '').upper()
        if not pair.endswith('USDT'):
            continue
        base = pair[:-4]
        if base not in wants or base in prices:
            continue
        price = entry.get('price')
        if price is None:
            continue
        try:
            price_val = float(price)
        except (TypeError, ValueError):
            continue
        prices[base] = price_val
        metas[base] = {
            'id': None,
            'name': base,
            'symbol': base,
            'source': 'binance'
        }
        if len(prices) == len(wants):
            break
    return prices, metas


def _load_cached_prices() -> Tuple[Dict[str, float], Dict[str, Dict]]:
    if not os.path.exists(CACHE_PATH):
        return {}, {}
    try:
        with open(CACHE_PATH, 'r') as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}, {}
    fetched_at = payload.get('fetched_at')
    if not fetched_at:
        return {}, {}
    try:
        fetched_dt = datetime.strptime(fetched_at, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
    except ValueError:
        return {}, {}
    age = (datetime.now(timezone.utc) - fetched_dt).total_seconds()
    if age > CACHE_TTL_SECONDS:
        return {}, {}
    prices: Dict[str, float] = {}
    metas: Dict[str, Dict] = {}
    for item in payload.get('data', []):
        symbol = (item.get('symbol') or '').upper()
        price = item.get('current_price')
        if not symbol or price is None:
            continue
        if symbol not in prices:
            prices[symbol] = float(price)
            metas[symbol] = {
                'id': item.get('id'),
                'name': item.get('name'),
                'symbol': symbol,
                'source': 'coingecko_cache'
            }
    return prices, metas


def _fetch_market_prices(symbols: List[str]) -> Tuple[Dict[str, float], Dict[str, Dict]]:
    cached_prices, cached_meta = _load_cached_prices()
    prices: Dict[str, float] = {}
    metas: Dict[str, Dict] = {}
    missing: List[str] = []
    for sym in symbols:
        price = cached_prices.get(sym)
        if price is not None:
            prices[sym] = price
            if cached_meta.get(sym):
                metas[sym] = cached_meta[sym]
        else:
            missing.append(sym)
    if missing:
        live_prices, live_meta = _fetch_market_prices_live(missing)
        prices.update(live_prices)
        metas.update(live_meta)
        missing = [sym for sym in symbols if sym not in prices]
    if missing:
        binance_prices, binance_meta = _fetch_binance_prices(missing)
        prices.update(binance_prices)
        metas.update(binance_meta)
    return prices, metas


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _ensure_trade_dirs():
    os.makedirs(TRADES_DIR, exist_ok=True)


def _load_json_file(path: str, default):
    if os.path.exists(path):
        try:
            with open(path, 'r') as handle:
                return json.load(handle)
        except json.JSONDecodeError:
            return default
    return default


def _write_json_file(path: str, data):
    _ensure_trade_dirs()
    with open(path, 'w') as handle:
        json.dump(data, handle, indent=2)


def _append_entry_event(entry: Dict):
    _ensure_trade_dirs()
    with open(ENTRY_EVENTS_PATH, 'a') as handle:
        handle.write(json.dumps(entry) + '\n')


def _load_entry_state() -> Dict:
    state = _load_json_file(ENTRY_STATE_PATH, {})
    return state if isinstance(state, dict) else {}


def _save_entry_state(state: Dict):
    _write_json_file(ENTRY_STATE_PATH, state)


def _parse_iso(ts: str):
    if not ts:
        return None
    value = ts
    if value.endswith('Z'):
        value = value[:-1] + '+00:00'
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _today_midnight_iso() -> str:
    now = datetime.now(timezone.utc)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight.strftime('%Y-%m-%dT%H:%M:%SZ')


def _load_tier_b_session_state() -> Dict:
    state = _load_json_file(TIER_B_GUARD_STATE_PATH, {})
    session_start = state.get('session_start')
    start_dt = _parse_iso(session_start) if session_start else None
    today = datetime.now(timezone.utc).date()
    if not start_dt or start_dt.date() != today:
        session_start = _today_midnight_iso()
    state['session_start'] = session_start
    state['realized_pnl'] = float(state.get('realized_pnl') or 0.0)
    return state


def _load_loss_streak_state() -> Dict:
    state = _load_json_file(LOSS_STREAK_STATE_PATH, {})
    if not isinstance(state, dict):
        return {}
    cooldown_until = _parse_iso(state.get('cooldown_until'))
    if cooldown_until and cooldown_until < datetime.now(timezone.utc):
        return {}
    return state


def _save_loss_streak_state(state: Dict):
    if state:
        _write_json_file(LOSS_STREAK_STATE_PATH, state)
    elif os.path.exists(LOSS_STREAK_STATE_PATH):
        os.remove(LOSS_STREAK_STATE_PATH)


def _recent_stop_loss_streak(trades: List[Dict], limit: int) -> bool:
    now = datetime.now(timezone.utc)
    today = now.date()
    relevant = []
    for trade in trades:
        exit_time = trade.get('exit_time') or trade.get('last_update')
        if not exit_time:
            continue
        exit_dt = _parse_iso(exit_time)
        if not exit_dt or exit_dt.date() != today:
            continue
        relevant.append((exit_dt, trade))
    relevant.sort(key=lambda item: item[0], reverse=True)
    streak = 0
    for _, trade in relevant:
        category = (trade.get('exit_category') or '').upper()
        reason = (trade.get('exit_reason') or '').lower()
        if category == 'SL' or 'stop loss' in reason:
            streak += 1
        else:
            break
        if streak >= limit:
            return True
    return False


def _update_loss_streak_pause(trades: List[Dict], state: Dict) -> Tuple[bool, Dict, bool, bool]:
    now = datetime.now(timezone.utc)
    cooldown_until = _parse_iso(state.get('cooldown_until') if state else None)
    paused = cooldown_until is not None and cooldown_until > now
    triggered = False
    released = False
    if not paused:
        if cooldown_until and cooldown_until <= now:
            released = True
        if _recent_stop_loss_streak(trades, LOSS_STREAK_MAX_SL):
            cooldown_until = now + timedelta(minutes=LOSS_STREAK_COOLDOWN_MINUTES)
            paused = True
            triggered = True
            state = {'cooldown_until': cooldown_until.strftime('%Y-%m-%dT%H:%M:%SZ')}
        else:
            state = {}
    return paused, state, triggered, released


def _load_market_state_payload() -> Dict:
    state = _load_json_file(MARKET_STATE_PATH, {})
    return state if isinstance(state, dict) else {}


def _select_trade_profile():
    state = _load_market_state_payload()
    mode = state.get('mode', 'baseline')
    profile = TRADE_PROFILES.get(mode, TRADE_PROFILES['baseline'])
    return profile, mode, state


def _compute_tier_b_realized(trades: List[Dict], session_start: str) -> float:
    start_dt = _parse_iso(session_start) if session_start else None
    total = 0.0
    for trade in trades:
        if (trade.get('tier') or 'A') != 'B':
            continue
        exit_time = trade.get('exit_time')
        if not exit_time:
            continue
        exit_dt = _parse_iso(exit_time)
        if not exit_dt:
            continue
        if start_dt and exit_dt < start_dt:
            continue
        try:
            pnl_pct = float(trade.get('pnl_percent') or 0.0)
            size_usd = float(trade.get('position_size_usd') or 0.0)
        except (TypeError, ValueError):
            continue
        total += size_usd * (pnl_pct / 100.0)
    return round(total, 4)


def _compute_tier_b_unrealized(open_positions: List[Dict]) -> float:
    total = 0.0
    for position in open_positions:
        if (position.get('tier') or 'A') != 'B':
            continue
        pnl_pct = float(position.get('pnl_percent') or 0.0)
        size = float(position.get('position_size_usd') or 0.0)
        total += size * pnl_pct / 100.0
    return round(total, 4)


def _load_session_guard_state() -> Dict:
    state = _load_json_file(SESSION_GUARD_PATH, {})
    session_start = state.get('session_start')
    start_dt = _parse_iso(session_start) if session_start else None
    today = datetime.now(timezone.utc).date()
    if not start_dt or start_dt.date() != today:
        state = {'session_start': _today_midnight_iso(), 'kill_switch': False, 'cooldown_runs': 0}
    state.setdefault('kill_switch', False)
    state.setdefault('cooldown_runs', 0)
    return state


def _save_session_guard_state(state: Dict):
    _write_json_file(SESSION_GUARD_PATH, state)


def _compute_session_realized(trades: List[Dict], session_start: str) -> float:
    start_dt = _parse_iso(session_start) if session_start else None
    total = 0.0
    for trade in trades:
        exit_time = trade.get('exit_time') or trade.get('last_update')
        if not exit_time:
            continue
        exit_dt = _parse_iso(exit_time)
        if not exit_dt or (start_dt and exit_dt < start_dt):
            continue
        try:
            pnl_pct = float(trade.get('pnl_percent') or 0.0)
            size_usd = float(trade.get('position_size_usd') or 0.0)
        except (TypeError, ValueError):
            continue
        total += size_usd * (pnl_pct / 100.0)
    return round(total, 4)


def _compute_session_unrealized(open_positions: List[Dict]) -> float:
    total = 0.0
    for position in open_positions:
        pnl_pct = float(position.get('pnl_percent') or 0.0)
        size = float(position.get('position_size_usd') or 0.0)
        total += size * pnl_pct / 100.0
    return round(total, 4)


def _current_heat(open_positions: List[Dict]) -> float:
    return round(sum(float(position.get('position_size_usd') or 0.0) for position in open_positions), 4)


def _tier_a_regime_ok(ranked: List[Dict]) -> bool:
    if not ranked:
        return False
    strong = 0
    total_score = 0.0
    for entry in ranked:
        score = float(entry.get('score') or 0.0)
        momentum = float(entry.get('momentum') or 0.0)
        volume = float(entry.get('volume') or 0.0)
        if (momentum >= TIER_A_REGIME_MIN_MOMENTUM and
                score >= TIER_A_REGIME_MIN_AVG_SCORE and
                volume >= TIER_A_REGIME_MIN_VOLUME):
            strong += 1
        total_score += score
    avg_score = total_score / len(ranked)
    return strong >= TIER_A_REGIME_MIN_STRONG_SIGNALS and avg_score >= TIER_A_REGIME_MIN_AVG_SCORE


def _is_in_cooldown(token: str, ranking_ts: str, state: Dict) -> bool:
    last_map = state.get('last_entry_ts') or {}
    last_iso = last_map.get(token)
    if not last_iso:
        return False
    last_dt = _parse_iso(last_iso)
    if not last_dt:
        return False
    current_iso = ranking_ts if ranking_ts.endswith('Z') else f"{ranking_ts}Z"
    current_dt = _parse_iso(current_iso)
    if not current_dt:
        return False
    return (current_dt - last_dt) < timedelta(minutes=TOKEN_COOLDOWN_MINUTES)


def _update_cooldown(token: str, ranking_ts: str, state: Dict):
    last_map = state.setdefault('last_entry_ts', {})
    iso = ranking_ts if ranking_ts.endswith('Z') else f"{ranking_ts}Z"
    last_map[token] = iso


def _meets_tier_rules(entry: Dict, rules: Dict) -> bool:
    persistence = int(entry.get('persistence') or 0)
    liquidity_score = float(entry.get('liquidity_score') or 0.0)
    liquidity_change = float(entry.get('liquidity_change_ratio') or 0.0)
    alignment = float(entry.get('momentum_alignment_score') or 0.0)
    buy_pressure = float(entry.get('buy_pressure_proxy') or 0.0)
    if persistence < rules['persistence']:
        return False
    if liquidity_score < rules['liquidity_score']:
        return False
    if liquidity_change < rules['liquidity_change_ratio']:
        return False
    if alignment < rules['alignment']:
        return False
    if buy_pressure < rules['buy_pressure']:
        return False
    return True


def _classify_tier(entry: Dict) -> str:
    if _meets_tier_rules(entry, TIER_A_RULES):
        return 'A'
    if _meets_tier_rules(entry, TIER_B_RULES):
        score = float(entry.get('score') or 0.0)
        if score >= TIER_B_MIN_SCORE:
            return 'B'
    return ''


def _compute_pnl(entry_price: float, current_price: float) -> float:
    if not entry_price:
        return 0.0
    return ((current_price - entry_price) / entry_price) * 100.0


def _refresh_open_positions(open_positions: List[Dict], prices: Dict[str, float], now_iso: str):
    updated: List[Dict] = []
    closed: List[Dict] = []
    for position in open_positions:
        token = (position.get('token') or '').upper()
        entry_price = float(position.get('entry_price') or 0) or 0.0
        current_price = prices.get(token)
        if current_price is None or entry_price == 0.0:
            updated.append(position)
            continue

        target_price = float(position.get('target_price') or (entry_price * (1 + TAKE_PROFIT_PCT / 100)))
        stop_price = float(position.get('stop_price') or (entry_price * (1 + STOP_LOSS_PCT / 100)))
        pnl_pct = _compute_pnl(entry_price, current_price)
        position_size_usd = float(position.get('position_size_usd') or 0.0)

        position.update({
            'current_price': round(current_price, 6),
            'last_update': now_iso,
            'target_price': round(target_price, 6),
            'stop_price': round(stop_price, 6),
            'pnl_percent': round(pnl_pct, 4)
        })

        exit_reason = None
        exit_category = None
        if current_price >= target_price:
            exit_reason = 'Take profit target hit'
            exit_category = 'TP'
        elif current_price <= stop_price:
            exit_reason = 'Stop loss hit'
            exit_category = 'SL'

        if exit_reason:
            trade_record = position.copy()
            trade_record.update({
                'status': 'closed',
                'exit_price': round(current_price, 6),
                'exit_time': now_iso,
                'exit_reason': exit_reason,
                'exit_category': exit_category,
                'pnl_percent': round(pnl_pct, 4),
                'pnl_usd': round(position_size_usd * (pnl_pct / 100.0), 4)
            })
            closed.append(trade_record)
        else:
            updated.append(position)
    return updated, closed


def _should_enter_trade(signal: Dict) -> bool:
    try:
        decision = RISK_MANAGER.risk_manager({
            'token': signal.get('token'),
            'persistence': signal.get('persistence'),
            'score': signal.get('score'),
            'risk_usd': signal.get('risk_usd', POSITION_SIZE_USD),
            'volume': signal.get('volume'),
            'momentum': signal.get('momentum'),
            'liquidity_score': signal.get('liquidity_score'),
            'liquidity_change_ratio': signal.get('liquidity_change_ratio')
        })
        return decision.get('decision') == 'APPROVED'
    except Exception:  # pragma: no cover
        return True


def _find_rotation_candidate(positions: List[Dict], signal_score: float, now_iso: str) -> Dict:
    if signal_score < TIER_B_ROTATION_MIN_SCORE:
        return None
    now_dt = _parse_iso(now_iso) or datetime.now(timezone.utc)
    candidate = None
    candidate_pnl = None
    for position in positions:
        if (position.get('tier') or 'A') != 'B':
            continue
        entry_time = position.get('entry_time') or position.get('last_update')
        entry_dt = _parse_iso(entry_time)
        if not entry_dt:
            continue
        hold_minutes = (now_dt - entry_dt).total_seconds() / 60.0
        if hold_minutes < TIER_B_ROTATION_MIN_HOLD_MINUTES:
            continue
        pnl_pct = float(position.get('pnl_percent') or 0.0)
        original_score = float(position.get('score') or 0.0)
        if pnl_pct > TIER_B_ROTATION_MIN_DRAWDOWN and (signal_score - original_score) < TIER_B_ROTATION_SCORE_GAP:
            continue
        if candidate is None or pnl_pct < candidate_pnl:
            candidate = position
            candidate_pnl = pnl_pct
    return candidate


def _close_position_for_rotation(position: Dict, price: float, now_iso: str) -> Dict:
    entry_price = float(position.get('entry_price') or 0.0)
    pnl_pct = _compute_pnl(entry_price, price)
    size_usd = float(position.get('position_size_usd') or 0.0)
    record = position.copy()
    record.update({
        'status': 'closed',
        'exit_price': round(price, 6),
        'exit_time': now_iso,
        'exit_reason': 'rotation_exit',
        'exit_category': 'ROT',
        'pnl_percent': round(pnl_pct, 4),
        'pnl_usd': round(size_usd * (pnl_pct / 100.0), 4)
    })
    return record


def _open_new_positions(open_positions: List[Dict], ranked: List[Dict], prices: Dict[str, float], ranking_ts: str,
                        price_meta: Dict[str, Dict], tier_b_open_count: int = 0, tier_b_paused: bool = False,
                        tier_a_regime_ok: bool = True, tier_a_open_count: int = 0, trade_profile: Dict = None,
                        now_iso: str = None):
    open_tokens = {position.get('token', '').upper() for position in open_positions}
    created: List[Dict] = []
    rotated: List[Dict] = []
    entry_state = _load_entry_state()
    state_changed = False
    profile = trade_profile or TRADE_PROFILES['baseline']
    tier_b_cap = profile.get('tier_b_max_positions', TIER_B_MAX_OPEN_POSITIONS)
    tier_a_cap = profile.get('tier_a_max_positions', 0)
    current_tier_b = tier_b_open_count
    current_tier_a = tier_a_open_count
    for entry in ranked:
        token = (entry.get('token') or entry.get('symbol') or '').upper()
        if not token or token in open_tokens:
            continue
        meta = price_meta.get(token) or {}
        tier = _classify_tier(entry)
        if not tier:
            continue
        if tier == 'B':
            if tier_b_paused:
                _append_entry_event({
                    'timestamp': _now_iso(),
                    'token': token,
                    'tier': tier,
                    'signal_score': entry.get('score'),
                    'persistence': entry.get('persistence'),
                    'reason': 'tier_b_paused_drawdown'
                })
                continue
            if current_tier_b >= tier_b_cap:
                candidate = _find_rotation_candidate(open_positions + created, float(entry.get('score') or 0.0), now_iso or _now_iso())
                if candidate:
                    candidate_token = (candidate.get('token') or '').upper()
                    exit_price = prices.get(candidate_token)
                    if exit_price:
                        rotation_trade = _close_position_for_rotation(candidate, exit_price, now_iso or _now_iso())
                        rotated.append(rotation_trade)
                        if candidate in open_positions:
                            open_positions.remove(candidate)
                        elif candidate in created:
                            created.remove(candidate)
                        open_tokens.discard(candidate_token)
                        current_tier_b -= 1
                        _append_entry_event({
                            'timestamp': _now_iso(),
                            'token': candidate_token,
                            'tier': 'B',
                            'reason': 'tier_b_rotation_exit',
                            'details': {'replacement': token, 'pnl_percent': rotation_trade.get('pnl_percent')}
                        })
                    else:
                        _append_entry_event({
                            'timestamp': _now_iso(),
                            'token': token,
                            'tier': tier,
                            'signal_score': entry.get('score'),
                            'persistence': entry.get('persistence'),
                            'reason': 'tier_b_rotation_failed_missing_price'
                        })
                        continue
                else:
                    _append_entry_event({
                        'timestamp': _now_iso(),
                        'token': token,
                        'tier': tier,
                        'signal_score': entry.get('score'),
                        'persistence': entry.get('persistence'),
                        'reason': 'tier_b_max_positions_reached'
                    })
                    continue
        else:
            if tier_a_cap and current_tier_a >= tier_a_cap:
                _append_entry_event({
                    'timestamp': _now_iso(),
                    'token': token,
                    'tier': tier,
                    'signal_score': entry.get('score'),
                    'persistence': entry.get('persistence'),
                    'reason': 'tier_a_max_positions_reached'
                })
                continue
            if not tier_a_regime_ok:
                _append_entry_event({
                    'timestamp': _now_iso(),
                    'token': token,
                    'tier': tier,
                    'signal_score': entry.get('score'),
                    'persistence': entry.get('persistence'),
                    'reason': 'tier_a_regime_blocked'
                })
                continue
        if _is_in_cooldown(token, ranking_ts, entry_state):
            continue
        price = prices.get(token)
        if price is None:
            continue
        position_size = profile['tier_a_size'] if tier == 'A' else profile['tier_b_size']
        signal_payload = {
            'token': token,
            'persistence': entry.get('persistence'),
            'score': entry.get('score'),
            'tier': tier,
            'volume': entry.get('volume'),
            'momentum': entry.get('momentum'),
            'liquidity_score': entry.get('liquidity_score'),
            'liquidity_change_ratio': entry.get('liquidity_change_ratio'),
            'risk_usd': position_size
        }
        if not _should_enter_trade(signal_payload):
            continue
        entry_time = ranking_ts if ranking_ts.endswith('Z') else f"{ranking_ts}Z"
        stop_pct = TIER_B_STOP_LOSS_PCT if tier == 'B' else STOP_LOSS_PCT
        position = {
            'token': token,
            'tier': tier,
            'coin_id': meta.get('id'),
            'entry_time': entry_time,
            'source_timestamp': ranking_ts,
            'entry_price': round(price, 6),
            'current_price': round(price, 6),
            'position_size_usd': position_size,
            'units': round(position_size / price, 6),
            'target_price': round(price * (1 + TAKE_PROFIT_PCT / 100), 6),
            'stop_price': round(price * (1 + stop_pct / 100), 6),
            'take_profit_pct': TAKE_PROFIT_PCT,
            'stop_loss_pct': STOP_LOSS_PCT,
            'persistence': entry.get('persistence'),
            'score': entry.get('score'),
            'momentum': entry.get('momentum'),
            'volume': entry.get('volume'),
            'liquidity_score': entry.get('liquidity_score'),
            'alignment_score': entry.get('momentum_alignment_score'),
            'buy_pressure_proxy': entry.get('buy_pressure_proxy'),
            'liquidity_change_ratio': entry.get('liquidity_change_ratio'),
            'volume_acceleration_ratio': entry.get('volume_acceleration_ratio'),
            'status': 'open',
            'last_update': entry_time,
            'trail_active': False,
            'partial_taken': False,
            'max_loss_pct': stop_pct
        }
        volume_usd = float(entry.get('volume') or 0.0)
        if volume_usd and volume_usd < MICROCAP_VOLUME_THRESHOLD:
            position['take_profit_pct'] = MICROCAP_TAKE_PROFIT_PCT
            position['target_price'] = round(price * (1 + MICROCAP_TAKE_PROFIT_PCT / 100), 6)
            position['microcap_profile'] = True
        atr_info = get_atr_for_symbol(token, meta)
        if atr_info:
            position.update({
                'atr_usd': atr_info['atr_usd'],
                'atr_pct': atr_info['atr_pct'],
                'atr_last_updated': atr_info['fetched_at'],
                'atr_source': atr_info['source']
            })
        if tier == 'B':
            position['custom_time_stop_hours'] = TIER_B_TIME_STOP_HOURS
            position['custom_no_movement_pct'] = TIER_B_NO_MOVE_PCT
        created.append(position)
        open_tokens.add(token)
        if tier == 'B':
            current_tier_b += 1
        else:
            current_tier_a += 1
        _update_cooldown(token, entry_time, entry_state)
        state_changed = True
        _append_entry_event({
            'timestamp': _now_iso(),
            'token': token,
            'tier': tier,
            'entry_price': position['entry_price'],
            'signal_score': entry.get('score'),
            'persistence': entry.get('persistence'),
            'price_source': meta.get('source'),
            'coin_id': meta.get('id'),
            'reason': 'new_position_created'
        })
    if state_changed:
        _save_entry_state(entry_state)
    return open_positions + created, created, rotated


def _build_summary(open_positions: List[Dict], closed_trades: List[Dict]) -> str:
    lines = ["Paper trading update", ""]
    lines.append("Open positions:")
    if open_positions:
        for position in sorted(open_positions, key=lambda p: p.get('token', '')):
            token = position.get('token', 'UNKNOWN')
            pnl = position.get('pnl_percent')
            if pnl is None:
                entry_price = float(position.get('entry_price') or 0)
                current_price = float(position.get('current_price') or entry_price)
                pnl = _compute_pnl(entry_price, current_price)
            lines.append(f"{token} {pnl:+.2f}%")
    else:
        lines.append("None")
    lines.append("")
    lines.append("Closed trades:")
    if closed_trades:
        for trade in closed_trades:
            token = trade.get('token', 'UNKNOWN')
            pnl = float(trade.get('pnl_percent') or 0.0)
            reason = trade.get('exit_category') or trade.get('exit_reason')
            lines.append(f"{token} {pnl:+.2f}% ({reason})")
    else:
        lines.append("None")
    return "\n".join(lines)


def _flatten_all_positions() -> Dict:
    _ensure_trade_dirs()
    open_positions = _load_json_file(OPEN_POSITIONS_PATH, [])
    trades_log = _load_json_file(TRADES_LOG_PATH, [])
    if not open_positions:
        summary = _build_summary([], [])
        now_iso = _now_iso()
        return {
            'timestamp': now_iso,
            'open_positions': [],
            'closed_trades': [],
            'new_positions': [],
            'summary': summary,
            'flattened': True,
            'trades_log_path': TRADES_LOG_PATH
        }

    symbols = sorted({(position.get('token') or '').upper() for position in open_positions if position.get('token')})
    prices, _ = _fetch_market_prices(symbols)
    now_iso = _now_iso()
    closed_trades: List[Dict] = []
    for position in open_positions:
        token = (position.get('token') or '').upper()
        entry_price = float(position.get('entry_price') or 0.0)
        current_price = float(position.get('current_price') or entry_price)
        exit_price = prices.get(token) or current_price or entry_price
        pnl_pct = _compute_pnl(entry_price, exit_price)
        size_usd = float(position.get('position_size_usd') or 0.0)
        pnl_usd = size_usd * (pnl_pct / 100.0)
        closed = dict(position)
        closed.update({
            'status': 'closed',
            'exit_time': now_iso,
            'exit_reason': 'manual_flatten',
            'exit_category': 'EXIT',
            'exit_price': exit_price,
            'pnl_percent': round(pnl_pct, 4),
            'pnl_usd': round(pnl_usd, 4),
            'last_update': now_iso
        })
        closed_trades.append(closed)

    trades_log.extend(closed_trades)
    _write_json_file(TRADES_LOG_PATH, trades_log)
    _write_json_file(OPEN_POSITIONS_PATH, [])
    summary = _build_summary([], closed_trades)

    return {
        'timestamp': now_iso,
        'open_positions': [],
        'closed_trades': closed_trades,
        'new_positions': [],
        'summary': summary,
        'flattened': True,
        'trades_log_path': TRADES_LOG_PATH
    }


def paper_trader() -> Dict:
    if os.environ.get('PAPER_TRADER_FLATTEN') == '1':
        return _flatten_all_positions()

    _ensure_trade_dirs()
    ranked, ranked_ts = _load_latest_ranked()
    trade_profile, market_mode, market_state = _select_trade_profile()
    tier_a_regime_ok = _tier_a_regime_ok(ranked) and (market_mode == 'high_opportunity')

    open_positions = _load_json_file(OPEN_POSITIONS_PATH, [])
    trades_log = _load_json_file(TRADES_LOG_PATH, [])

    tier_b_state = _load_tier_b_session_state()
    tier_b_realized = _compute_tier_b_realized(trades_log, tier_b_state['session_start'])
    tier_b_state['realized_pnl'] = tier_b_realized
    tier_b_state.setdefault('unrealized_pnl', 0.0)

    price_symbols = {position.get('token', '').upper() for position in open_positions}
    price_symbols.update((entry.get('token') or '').upper() for entry in ranked)
    price_symbols.discard('')

    prices, price_meta = _fetch_market_prices(sorted(price_symbols))

    now_iso = _now_iso()
    refreshed_positions, closed_trades = _refresh_open_positions(open_positions, prices, now_iso)
    tier_b_unrealized = _compute_tier_b_unrealized(refreshed_positions)
    updated_log = trades_log[:]
    if closed_trades:
        updated_log.extend(closed_trades)

    loss_streak_state = _load_loss_streak_state()
    loss_streak_paused, loss_streak_state, loss_triggered, loss_released = _update_loss_streak_pause(updated_log, loss_streak_state)
    _save_loss_streak_state(loss_streak_state)
    if loss_triggered:
        _append_entry_event({
            'timestamp': now_iso,
            'token': '-',
            'tier': 'B',
            'reason': 'tier_b_loss_streak_pause',
            'details': {'cooldown_until': loss_streak_state.get('cooldown_until')}
        })
    elif loss_released:
        _append_entry_event({
            'timestamp': now_iso,
            'token': '-',
            'tier': 'B',
            'reason': 'tier_b_loss_streak_resume'
        })

    net_guard_pnl = tier_b_realized + tier_b_unrealized
    tier_b_state['unrealized_pnl'] = tier_b_unrealized
    tier_b_state['net_pnl'] = round(net_guard_pnl, 4)
    tier_b_paused = loss_streak_paused or (net_guard_pnl <= TIER_B_SESSION_MAX_DRAWDOWN_USD)
    tier_b_state['paused'] = tier_b_paused
    _write_json_file(TIER_B_GUARD_STATE_PATH, tier_b_state)

    session_guard = _load_session_guard_state()
    session_realized = _compute_session_realized(updated_log, session_guard['session_start'])
    session_unrealized = _compute_session_unrealized(refreshed_positions)
    current_heat = _current_heat(refreshed_positions)
    exposure_capacity = (
        trade_profile.get('tier_a_size', TIER_A_POSITION_SIZE) * trade_profile.get('tier_a_max_positions', 0) +
        trade_profile.get('tier_b_size', TIER_B_POSITION_SIZE) * trade_profile.get('tier_b_max_positions', 0)
    )
    heat_limit = SESSION_GUARD_HEAT_DRAWDOWN_PCT * current_heat if current_heat else 0.0
    exposure_limit = SESSION_GUARD_MAX_DRAWDOWN_PCT * exposure_capacity if exposure_capacity else SESSION_GUARD_MAX_DRAWDOWN_PCT * current_heat
    guard_threshold = exposure_limit
    if heat_limit:
        guard_threshold = min(exposure_limit, heat_limit)
    net_session_pnl = round(session_realized + session_unrealized, 4)
    kill_switch_triggered = guard_threshold is not None and guard_threshold < 0 and net_session_pnl <= guard_threshold

    if kill_switch_triggered:
        if not session_guard.get('kill_switch'):
            _append_entry_event({
                'timestamp': _now_iso(),
                'token': '-',
                'tier': '-',
                'reason': 'session_guard_triggered',
                'details': {'net_pnl': net_session_pnl, 'threshold': guard_threshold}
            })
        session_guard['kill_switch'] = True
        session_guard['cooldown_runs'] = SESSION_GUARD_COOLDOWN_CYCLES
        session_guard['last_triggered_at'] = now_iso
    elif session_guard.get('kill_switch'):
        remaining = max(session_guard.get('cooldown_runs', 0) - 1, 0)
        session_guard['cooldown_runs'] = remaining
        if remaining <= 0 and net_session_pnl > guard_threshold:
            session_guard['kill_switch'] = False
            session_guard['last_recovered_at'] = now_iso
            _append_entry_event({
                'timestamp': _now_iso(),
                'token': '-',
                'tier': '-',
                'reason': 'session_guard_reset',
                'details': {'net_pnl': net_session_pnl}
            })

    session_guard.update({
        'net_pnl': net_session_pnl,
        'realized_pnl': session_realized,
        'unrealized_pnl': session_unrealized,
        'current_heat': current_heat,
        'threshold': guard_threshold,
        'mode': market_mode
    })

    session_guard_blocked = session_guard.get('kill_switch', False)

    tier_b_open_count = sum(1 for position in refreshed_positions if (position.get('tier') or 'A') == 'B')
    tier_a_open_count = sum(1 for position in refreshed_positions if (position.get('tier') or 'A') == 'A')
    if session_guard_blocked:
        _append_entry_event({
            'timestamp': _now_iso(),
            'token': '-',
            'tier': '-',
            'reason': 'session_guard_blocked',
            'details': {'net_pnl': session_guard.get('net_pnl'), 'threshold': session_guard.get('threshold')}
        })
        final_positions = refreshed_positions
        new_positions = []
        rotated_trades = []
    else:
        final_positions, new_positions, rotated_trades = _open_new_positions(
            refreshed_positions,
            ranked,
            prices,
            ranked_ts,
            price_meta=price_meta,
            tier_b_open_count=tier_b_open_count,
            tier_b_paused=tier_b_paused,
            tier_a_regime_ok=tier_a_regime_ok,
            tier_a_open_count=tier_a_open_count,
            trade_profile=trade_profile,
            now_iso=now_iso
        )

    if rotated_trades:
        updated_log.extend(rotated_trades)
        closed_trades.extend(rotated_trades)

    _write_json_file(OPEN_POSITIONS_PATH, final_positions)
    _write_json_file(TRADES_LOG_PATH, updated_log)

    summary = _build_summary(final_positions, closed_trades)

    _save_session_guard_state(session_guard)

    result = {
        'timestamp': now_iso,
        'signal_timestamp': ranked_ts,
        'open_positions': final_positions,
        'closed_trades': closed_trades,
        'new_positions': new_positions,
        'summary': summary,
        'open_positions_path': OPEN_POSITIONS_PATH,
        'trades_log_path': TRADES_LOG_PATH,
        'tier_b_guard': {
            'session_start': tier_b_state['session_start'],
            'realized_pnl': tier_b_state['realized_pnl'],
            'unrealized_pnl': tier_b_state.get('unrealized_pnl', 0.0),
            'net_pnl': tier_b_state.get('net_pnl', tier_b_state['realized_pnl'] + tier_b_state.get('unrealized_pnl', 0.0)),
            'paused': tier_b_paused,
            'max_positions': trade_profile.get('tier_b_max_positions', TIER_B_MAX_OPEN_POSITIONS),
            'drawdown_limit': TIER_B_SESSION_MAX_DRAWDOWN_USD
        },
        'tier_a_regime_ok': tier_a_regime_ok,
        'market_mode': market_mode,
        'trade_profile': trade_profile,
        'market_state': market_state,
        'session_guard': session_guard
    }

    return result


if __name__ == '__main__':
    output = paper_trader()
    print(json.dumps(output, indent=2))
