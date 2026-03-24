import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE = Path('/home/lokiai/.openclaw/workspace')
CACHE_DIR = WORKSPACE / 'cache'
TRADES_DIR = WORKSPACE / 'paper_trades'
MARKET_STATE_PATH = CACHE_DIR / 'market_state.json'
COINBASE_WS_STATE_PATH = CACHE_DIR / 'coinbase_ws_state.json'
COINBASE_TICKERS_PATH = CACHE_DIR / 'coinbase_tickers.json'

V2_OPEN_POSITIONS_PATH = TRADES_DIR / 'open_positions_v2.json'
V2_TRADES_LOG_PATH = TRADES_DIR / 'trades_log_v2.json'
V2_STATE_PATH = TRADES_DIR / 'paper_trader_v2_state.json'
V2_DECISIONS_PATH = TRADES_DIR / 'paper_trader_v2_decisions.jsonl'
V2_AUDIT_SUMMARY_PATH = TRADES_DIR / 'paper_trader_v2_audit_summary.json'

MAX_SLOTS = 3
TIER_A_MIN_SCORE = 0.42
TIER_B_MIN_SCORE = 0.30
FRESHNESS_LIMIT_SECONDS = 180
TIER_A_MIN_DRIFT_300S = 0.10
TIER_B_MIN_DRIFT_300S = 0.08
TIER_B_MIN_PERSISTENCE = 2
COOLDOWN_MINUTES = 45
TIER_A_STOP_LOSS_PCT = -4.0
TIER_B_STOP_LOSS_PCT = -3.0
TIER_A_TIMEOUT_MINUTES = 210
TIER_B_TIMEOUT_MINUTES = 90
NO_MOVE_THRESHOLD_PCT = 0.20
TIER_A_TRIM_LEVELS = [1.5, 3.0, 5.0]
TIER_B_TRIM_LEVELS = [1.0, 2.0, 3.5]
TIER_A_TRAIL_AFTER_FIRST = 0.7
TIER_A_TRAIL_AFTER_SECOND = 1.2
TIER_B_TRAIL_AFTER_FIRST = 0.5
TIER_B_TRAIL_AFTER_SECOND = 0.9
FAKE_PUMP_DRIFT_THRESHOLD = 0.35
FAKE_PUMP_DE_RISK_PCT = 25


def _load_json(path: Path, default: Any):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(payload, indent=2))
    tmp.replace(path)


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as fh:
        fh.write(json.dumps(payload) + '\n')


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _iso_to_dt(value: str | None):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _symbol_to_product_id(symbol: str) -> str:
    return f'{symbol.upper()}-USD'


def _load_current_inputs() -> tuple[dict, dict, dict]:
    market_state = _load_json(MARKET_STATE_PATH, {})
    ws_state = _load_json(COINBASE_WS_STATE_PATH, {})
    tickers = _load_json(COINBASE_TICKERS_PATH, {})
    return market_state, ws_state, tickers


def _load_trader_state() -> dict:
    state = _load_json(V2_STATE_PATH, {})
    if not isinstance(state, dict):
        state = {}
    state.setdefault('last_entries', {})
    return state


def _candidate_tier(candidate: dict, ticker: dict) -> str:
    score = float(candidate.get('score') or 0.0)
    freshness = ticker.get('freshness_seconds')
    freshness = float(freshness) if freshness is not None else None
    drift = float(ticker.get('drift_300s') or 0.0)
    trend = (candidate.get('trend') or candidate.get('status') or '').lower()
    momentum = float(candidate.get('momentum') or 0.0)

    if freshness is None or freshness > FRESHNESS_LIMIT_SECONDS:
        return ''
    if drift <= 0:
        return ''
    if trend in {'isolated spike', 'fading'}:
        return ''
    if drift >= FAKE_PUMP_DRIFT_THRESHOLD and momentum < 12.0:
        return ''

    persistence = int(candidate.get('persistence') or 0)

    if score >= TIER_A_MIN_SCORE and drift >= TIER_A_MIN_DRIFT_300S:
        return 'A'
    if score >= TIER_B_MIN_SCORE and drift >= TIER_B_MIN_DRIFT_300S and persistence >= TIER_B_MIN_PERSISTENCE:
        return 'B'
    return ''


def _cooldown_blocked(symbol: str, state: dict) -> bool:
    last_entries = state.get('last_entries', {})
    dt = _iso_to_dt(last_entries.get(symbol))
    if not dt:
        return False
    return (datetime.now(timezone.utc) - dt).total_seconds() < COOLDOWN_MINUTES * 60


def _normalized_guardrails(tier: str) -> dict:
    return {
        'stop_loss_pct': TIER_A_STOP_LOSS_PCT if tier == 'A' else TIER_B_STOP_LOSS_PCT,
        'profit_levels_pct': TIER_A_TRIM_LEVELS if tier == 'A' else TIER_B_TRIM_LEVELS,
        'timeout_minutes': TIER_A_TIMEOUT_MINUTES if tier == 'A' else TIER_B_TIMEOUT_MINUTES,
        'trail_after_first_pct': TIER_A_TRAIL_AFTER_FIRST if tier == 'A' else TIER_B_TRAIL_AFTER_FIRST,
        'trail_after_second_pct': TIER_A_TRAIL_AFTER_SECOND if tier == 'A' else TIER_B_TRAIL_AFTER_SECOND,
    }


def _normalize_open_positions(open_positions: list[dict]) -> list[dict]:
    normalized = []
    for idx, position in enumerate(open_positions, start=1):
        tier = position.get('tier', 'B')
        position.setdefault('slot_id', idx)
        position.setdefault('status', 'open')
        position.setdefault('trade_state', 'ACTIVE')
        position.setdefault('move_character', 'building')
        position.setdefault('current_price', position.get('entry_price'))
        position.setdefault('pnl_percent', 0.0)
        position.setdefault('time_in_trade_minutes', 0)
        position.setdefault('highest_pnl_percent', max(float(position.get('pnl_percent') or 0.0), float(position.get('highest_pnl_percent') or 0.0)))
        position.setdefault('trim_step', 0)
        position.setdefault('trail_active', False)
        position.setdefault('trail_distance_pct', 0.0)
        position.setdefault('remaining_size_pct', 100.0)
        position.setdefault('de_risked_fake_pump', False)
        position['guardrails'] = _normalized_guardrails(tier)
        normalized.append(position)
    return normalized


def _build_shortlist(market_state: dict, tickers: dict, state: dict) -> list[dict]:
    candidates = []
    for item in market_state.get('top_opportunities', []):
        symbol = (item.get('token') or '').upper()
        if not symbol:
            continue
        product_id = _symbol_to_product_id(symbol)
        ticker = tickers.get(product_id)
        if not ticker or ticker.get('price') is None:
            continue
        if _cooldown_blocked(symbol, state):
            continue
        tier = _candidate_tier(item, ticker)
        if not tier:
            continue
        candidates.append({
            'symbol': symbol,
            'product_id': product_id,
            'tier': tier,
            'score': float(item.get('score') or 0.0),
            'momentum': float(item.get('momentum') or 0.0),
            'persistence': int(item.get('persistence') or 0),
            'trend': item.get('trend') or item.get('status') or 'unknown',
            'price': float(ticker.get('price')),
            'drift_300s': float(ticker.get('drift_300s') or 0.0),
            'freshness_seconds': float(ticker.get('freshness_seconds') or 0.0),
            'entry_reason': 'scanner_rank_plus_websocket_confirmation',
        })
    candidates.sort(key=lambda x: (x['tier'] == 'A', x['score'], abs(x['drift_300s'])), reverse=True)
    return candidates


def _classify_move_character(position: dict, ticker: dict | None) -> str:
    drift = float((ticker or {}).get('drift_300s') or 0.0)
    pnl = float(position.get('pnl_percent') or 0.0)
    freshness = float((ticker or {}).get('freshness_seconds') or 9999.0)
    trend = (position.get('trend') or '').lower()

    if freshness > FRESHNESS_LIMIT_SECONDS:
        return 'stale'
    if drift >= FAKE_PUMP_DRIFT_THRESHOLD and pnl < 0.75:
        return 'fake_pump'
    if pnl > 1.5 and drift > 0.20:
        return 'accelerating'
    if drift > 0.35:
        return 'spike'
    if pnl > 0 and 'steady' in trend:
        return 'steady'
    if drift < -0.15:
        return 'fading'
    if abs(drift) < 0.03:
        return 'stalling'
    return 'building'


def _tier_profit_profile(tier: str) -> tuple[list[float], float, float]:
    if tier == 'A':
        return TIER_A_TRIM_LEVELS, TIER_A_TRAIL_AFTER_FIRST, TIER_A_TRAIL_AFTER_SECOND
    return TIER_B_TRIM_LEVELS, TIER_B_TRAIL_AFTER_FIRST, TIER_B_TRAIL_AFTER_SECOND


def _refresh_positions(open_positions: list[dict], tickers: dict[str, dict]) -> tuple[list[dict], list[dict]]:
    now = datetime.now(timezone.utc)
    updated = []
    closed = []
    for position in open_positions:
        product_id = position.get('product_id')
        ticker = tickers.get(product_id or '')
        if not ticker or ticker.get('price') is None:
            updated.append(position)
            continue
        current_price = float(ticker.get('price'))
        entry_price = float(position.get('entry_price') or current_price)
        pnl_percent = ((current_price - entry_price) / entry_price) * 100 if entry_price else 0.0
        entry_dt = _iso_to_dt(position.get('entry_time')) or now
        time_in_trade_minutes = int((now - entry_dt).total_seconds() // 60)
        tier = position.get('tier', 'B')
        timeout_limit = TIER_A_TIMEOUT_MINUTES if tier == 'A' else TIER_B_TIMEOUT_MINUTES
        stop_loss_pct = TIER_A_STOP_LOSS_PCT if tier == 'A' else TIER_B_STOP_LOSS_PCT
        trim_levels, trail_first, trail_second = _tier_profit_profile(tier)
        move_character = _classify_move_character(position, ticker)
        highest_pnl = max(float(position.get('highest_pnl_percent') or 0.0), pnl_percent)
        trim_step = int(position.get('trim_step') or 0)
        trail_active = bool(position.get('trail_active'))
        de_risked = bool(position.get('de_risked_fake_pump'))
        remaining_size_pct = float(position.get('remaining_size_pct') or 100.0)
        trade_state = position.get('trade_state', 'ACTIVE')
        drift_300s = float(ticker.get('drift_300s') or 0.0)

        for idx, level in enumerate(trim_levels, start=1):
            if highest_pnl >= level and trim_step < idx:
                trim_step = idx
                trade_state = f'TRIM_{idx}'
                if idx == 1:
                    trail_active = True
                    remaining_size_pct = 75.0
                elif idx == 2:
                    remaining_size_pct = 50.0
                elif idx == 3:
                    remaining_size_pct = 35.0
                _append_jsonl(V2_DECISIONS_PATH, {
                    'timestamp': _now_iso(),
                    'action': f'trim_{idx}',
                    'token': position.get('token'),
                    'tier': tier,
                    'pnl_percent': round(pnl_percent, 4),
                    'remaining_size_pct': remaining_size_pct,
                    'move_character': move_character,
                })

        if move_character == 'spike' and drift_300s >= FAKE_PUMP_DRIFT_THRESHOLD and not de_risked:
            de_risked = True
            trade_state = 'DE_RISKED'
            remaining_size_pct = min(remaining_size_pct, 100.0 - FAKE_PUMP_DE_RISK_PCT)
            _append_jsonl(V2_DECISIONS_PATH, {
                'timestamp': _now_iso(),
                'action': 'de_risk_fake_pump',
                'token': position.get('token'),
                'tier': tier,
                'pnl_percent': round(pnl_percent, 4),
                'remaining_size_pct': remaining_size_pct,
                'drift_300s': drift_300s,
            })

        active_trail = 0.0
        if trail_active:
            active_trail = trail_second if trim_step >= 2 else trail_first

        if trade_state.startswith('TRIM_'):
            display_state = trade_state
        elif de_risked:
            display_state = 'DE_RISKED'
        elif trail_active:
            display_state = 'TRAILING'
        elif move_character in {'accelerating', 'steady', 'building'}:
            display_state = 'ACTIVE'
        elif move_character in {'stalling', 'fading', 'fake_pump', 'stale'}:
            display_state = 'AT_RISK'
        else:
            display_state = 'ACTIVE'

        position.update({
            'current_price': current_price,
            'pnl_percent': round(pnl_percent, 4),
            'time_in_trade_minutes': time_in_trade_minutes,
            'last_update': _now_iso(),
            'move_character': move_character,
            'websocket_drift_300s': drift_300s,
            'websocket_freshness_seconds': float(ticker.get('freshness_seconds') or 0.0),
            'highest_pnl_percent': round(highest_pnl, 4),
            'trim_step': trim_step,
            'trail_active': trail_active,
            'trail_distance_pct': active_trail,
            'remaining_size_pct': round(remaining_size_pct, 2),
            'de_risked_fake_pump': de_risked,
            'trade_state': display_state,
        })

        exit_reason = None
        exit_category = None
        if pnl_percent <= stop_loss_pct:
            exit_reason = 'stop_loss'
            exit_category = 'SL'
        elif trail_active and highest_pnl > 0 and (highest_pnl - pnl_percent) >= active_trail:
            exit_reason = 'trailing_exit'
            exit_category = 'TRAIL'
            trade_state = 'TRAILING'
        elif time_in_trade_minutes >= timeout_limit and pnl_percent <= 0:
            exit_reason = 'timeout'
            exit_category = 'TIME'
        elif time_in_trade_minutes >= 30 and abs(pnl_percent) < NO_MOVE_THRESHOLD_PCT:
            exit_reason = 'no_move'
            exit_category = 'NM'
        elif de_risked and move_character in {'fading', 'stalling'} and pnl_percent < 0.25:
            exit_reason = 'fake_pump_confirmed'
            exit_category = 'FP'

        if exit_reason:
            closed_position = dict(position)
            closed_position.update({
                'status': 'closed',
                'trade_state': 'CLOSED',
                'exit_time': _now_iso(),
                'exit_reason': exit_reason,
                'exit_category': exit_category,
            })
            closed.append(closed_position)
            _append_jsonl(V2_DECISIONS_PATH, {
                'timestamp': _now_iso(),
                'action': 'close_position',
                'token': position.get('token'),
                'tier': tier,
                'pnl_percent': round(pnl_percent, 4),
                'exit_reason': exit_reason,
                'exit_category': exit_category,
                'move_character': move_character,
            })
        else:
            updated.append(position)
    return updated, closed


def _open_slots(shortlist: list[dict], open_positions: list[dict], state: dict) -> tuple[list[dict], list[dict]]:
    current_symbols = {(p.get('token') or '').upper() for p in open_positions}
    new_positions = []
    now_iso = _now_iso()
    for candidate in shortlist:
        if len(open_positions) + len(new_positions) >= MAX_SLOTS:
            break
        if candidate['symbol'] in current_symbols:
            continue
        position = {
            'slot_id': len(open_positions) + len(new_positions) + 1,
            'token': candidate['symbol'],
            'product_id': candidate['product_id'],
            'tier': candidate['tier'],
            'status': 'open',
            'trade_state': 'ACTIVE',
            'move_character': 'building',
            'entry_time': now_iso,
            'last_update': now_iso,
            'entry_price': candidate['price'],
            'current_price': candidate['price'],
            'pnl_percent': 0.0,
            'time_in_trade_minutes': 0,
            'scanner_score': candidate['score'],
            'momentum': candidate['momentum'],
            'persistence': candidate['persistence'],
            'trend': candidate['trend'],
            'entry_reason': candidate['entry_reason'],
            'websocket_drift_300s': candidate['drift_300s'],
            'websocket_freshness_seconds': candidate['freshness_seconds'],
            'guardrails': _normalized_guardrails(candidate['tier']),
            'highest_pnl_percent': 0.0,
            'trim_step': 0,
            'trail_active': False,
            'trail_distance_pct': 0.0,
            'remaining_size_pct': 100.0,
            'de_risked_fake_pump': False,
        }
        new_positions.append(position)
        state.setdefault('last_entries', {})[candidate['symbol']] = now_iso
        _append_jsonl(V2_DECISIONS_PATH, {
            'timestamp': now_iso,
            'action': 'open_position',
            'token': candidate['symbol'],
            'tier': candidate['tier'],
            'score': candidate['score'],
            'drift_300s': candidate['drift_300s'],
            'freshness_seconds': candidate['freshness_seconds'],
            'reason': candidate['entry_reason'],
        })
    return open_positions + new_positions, new_positions


def _build_audit_summary(open_positions: list[dict], trades_log: list[dict], summary: dict) -> dict:
    closed_count = len(trades_log)
    wins = [t for t in trades_log if float(t.get('pnl_percent') or 0.0) > 0]
    losses = [t for t in trades_log if float(t.get('pnl_percent') or 0.0) <= 0]
    avg_win = round(sum(float(t.get('pnl_percent') or 0.0) for t in wins) / len(wins), 4) if wins else 0.0
    avg_loss = round(sum(float(t.get('pnl_percent') or 0.0) for t in losses) / len(losses), 4) if losses else 0.0
    return {
        'timestamp': _now_iso(),
        'mode': summary.get('mode'),
        'active_slot_count': len(open_positions),
        'closed_trade_count': closed_count,
        'win_count': len(wins),
        'loss_count': len(losses),
        'avg_win_pct': avg_win,
        'avg_loss_pct': avg_loss,
        'latest_closed': trades_log[-5:],
        'latest_open': open_positions,
    }


def paper_trader_v2() -> dict:
    market_state, ws_state, tickers = _load_current_inputs()
    state = _load_trader_state()
    open_positions = _normalize_open_positions(_load_json(V2_OPEN_POSITIONS_PATH, []))
    trades_log = _load_json(V2_TRADES_LOG_PATH, [])

    refreshed_positions, closed_positions = _refresh_positions(open_positions, tickers)
    if closed_positions:
        trades_log.extend(closed_positions)

    shortlist = _build_shortlist(market_state, tickers, state)
    updated_positions, new_positions = _open_slots(shortlist, refreshed_positions, state)

    summary = {
        'timestamp': _now_iso(),
        'mode': 'watch' if not updated_positions else 'engaged',
        'active_slot_count': len(updated_positions),
        'shortlist_count': len(shortlist),
        'new_positions_count': len(new_positions),
        'closed_positions_count': len(closed_positions),
        'tier_a_candidates': sum(1 for c in shortlist if c['tier'] == 'A'),
        'tier_b_candidates': sum(1 for c in shortlist if c['tier'] == 'B'),
        'websocket_connected': bool(ws_state.get('connected')),
        'top_candidates': shortlist[:5],
    }

    audit_summary = _build_audit_summary(updated_positions, trades_log, summary)

    _write_json(V2_OPEN_POSITIONS_PATH, updated_positions)
    _write_json(V2_TRADES_LOG_PATH, trades_log)
    _write_json(V2_STATE_PATH, state)
    _write_json(V2_AUDIT_SUMMARY_PATH, audit_summary)

    return {
        'summary': summary,
        'open_positions_path': str(V2_OPEN_POSITIONS_PATH),
        'trades_log_path': str(V2_TRADES_LOG_PATH),
        'state_path': str(V2_STATE_PATH),
        'audit_summary_path': str(V2_AUDIT_SUMMARY_PATH),
        'open_positions': updated_positions,
        'closed_positions': closed_positions,
        'new_positions': new_positions,
        'audit_summary': audit_summary,
    }


if __name__ == '__main__':
    print(json.dumps(paper_trader_v2(), indent=2))
