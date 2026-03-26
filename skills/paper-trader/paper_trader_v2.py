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
V2_CANDIDATE_EVALS_PATH = TRADES_DIR / 'v2_candidate_evaluations.jsonl'
V2_POSITION_SNAPSHOTS_PATH = TRADES_DIR / 'v2_position_snapshots.jsonl'
V2_EXIT_EVENTS_PATH = TRADES_DIR / 'v2_exit_events.jsonl'
V2_AUDIT_SUMMARY_PATH = TRADES_DIR / 'paper_trader_v2_audit_summary.json'
V2_FUNNEL_SUMMARY_PATH = TRADES_DIR / 'v2_entry_funnel_summary.json'

MAX_SLOTS = 3
CANDIDATE_BENCH_LIMIT = 8
ENTRY_MIN_SCORE = 0.40
HIGH_CONFIDENCE_SCORE = 0.52
FRESHNESS_LIMIT_SECONDS = 180
ENTRY_MIN_DRIFT_300S = 0.03
HIGH_CONFIDENCE_MIN_DRIFT_300S = 0.06
ENTRY_MIN_PERSISTENCE = 4
COOLDOWN_MINUTES = 30
STOP_LOSS_PCT = -3.0
TIMEOUT_MINUTES = 45
NO_MOVE_THRESHOLD_PCT = 0.10
NO_MOVE_MINUTES = 10
TRIM_LEVELS = [0.40, 1.05, 2.25]
TRAIL_AFTER_FIRST = 0.2
TRAIL_AFTER_SECOND = 0.48
FAKE_PUMP_DRIFT_THRESHOLD = 0.35
FAKE_PUMP_DE_RISK_PCT = 25
EARLY_PROTECT_PNL_PCT = 0.28
EARLY_PROTECT_GIVEBACK_PCT = 0.18
FAILED_CONTINUATION_MINUTES = 12
FAILED_CONTINUATION_PEAK_PCT = 0.35
FAILED_CONTINUATION_RETAIN_PCT = 0.08
MODEST_CONTINUATION_MINUTES = 16
MODEST_CONTINUATION_PEAK_PCT = 0.20
MODEST_CONTINUATION_LOSS_PCT = -0.25
STRUCTURE_MIN_DRIFT_900S = -0.30
STRUCTURE_MAX_DRIFT_300S = 0.75
FULL_CONTINUATION_MIN_DRIFT_300S = 0.06
EARLY_RECLAIM_MIN_DRIFT_300S = -0.01
PULLBACK_RECLAIM_MIN_SCORE = 0.50


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
    state.setdefault('symbol_state', {})
    return state


def _get_symbol_state(state: dict, symbol: str) -> dict:
    symbol_state = state.setdefault('symbol_state', {})
    entry = symbol_state.get(symbol)
    if not isinstance(entry, dict):
        entry = {}
    entry.setdefault('lifecycle', 'idle')
    entry.setdefault('last_exit_reason', None)
    entry.setdefault('last_exit_pnl_percent', None)
    entry.setdefault('last_peak_pnl_percent', None)
    entry.setdefault('last_entry_at', state.get('last_entries', {}).get(symbol))
    entry.setdefault('last_exit_at', None)
    entry.setdefault('reentry_blocked_until', None)
    symbol_state[symbol] = entry
    return entry


def _set_symbol_reentry_state(state: dict, symbol: str, *, lifecycle: str, exit_reason: str | None = None, pnl_percent: float | None = None, highest_pnl: float | None = None, blocked_minutes: int = COOLDOWN_MINUTES) -> None:
    entry = _get_symbol_state(state, symbol)
    now = datetime.now(timezone.utc)
    entry['lifecycle'] = lifecycle
    entry['last_exit_reason'] = exit_reason
    entry['last_exit_pnl_percent'] = pnl_percent
    entry['last_peak_pnl_percent'] = highest_pnl
    entry['last_exit_at'] = now.replace(microsecond=0).isoformat()
    entry['reentry_blocked_until'] = (now + timedelta(minutes=blocked_minutes)).replace(microsecond=0).isoformat()


def _mark_symbol_entry(state: dict, symbol: str) -> None:
    now_iso = _now_iso()
    state.setdefault('last_entries', {})[symbol] = now_iso
    entry = _get_symbol_state(state, symbol)
    entry['lifecycle'] = 'active'
    entry['last_entry_at'] = now_iso
    entry['last_exit_reason'] = None
    entry['last_exit_pnl_percent'] = None
    entry['last_peak_pnl_percent'] = None
    entry['last_exit_at'] = None
    entry['reentry_blocked_until'] = None


def _reentry_decision(symbol: str, state: dict, candidate: dict | None = None, ticker: dict | None = None) -> tuple[bool, str | None]:
    last_entries = state.get('last_entries', {})
    dt = _iso_to_dt(last_entries.get(symbol))
    entry = _get_symbol_state(state, symbol)
    blocked_until = _iso_to_dt(entry.get('reentry_blocked_until'))
    now = datetime.now(timezone.utc)
    lifecycle = entry.get('lifecycle') or 'idle'
    if lifecycle == 'idle' and not blocked_until:
        return True, None
    if not dt and not blocked_until:
        return True, None

    candidate = candidate or {}
    ticker = ticker or {}
    score = float(candidate.get('score') or 0.0)
    persistence = int(candidate.get('persistence') or 0)
    drift_300s = float(ticker.get('drift_300s') or 0.0)
    drift_900s = float(ticker.get('drift_900s') or 0.0)
    freshness = float(ticker.get('freshness_seconds') or 9999.0)
    momentum = float(candidate.get('momentum') or 0.0)

    has_reset = drift_300s <= -0.05 or drift_900s <= -0.02 or freshness > 90
    strong_reclaim = (
        score >= 0.72 and
        persistence >= 5 and
        freshness <= FRESHNESS_LIMIT_SECONDS and
        drift_300s >= 0.12 and
        drift_900s >= 0.0 and
        momentum >= 3.0
    )
    exceptional_reclaim = (
        score >= 0.82 and
        persistence >= 5 and
        freshness <= 45 and
        drift_300s >= 0.20 and
        drift_900s >= 0.05
    )

    if blocked_until and now >= blocked_until:
        return True, None
    if exceptional_reclaim:
        return True, 'reclaimed_strength'
    if has_reset and strong_reclaim:
        return True, 'reset_and_reclaim'

    if lifecycle in {'choppy', 'exhausted'}:
        return False, 'leader_exhausted'
    if lifecycle == 'needs_reset':
        return False, 'needs_reset'
    if lifecycle == 'active':
        return False, 'cooldown'
    return True, None


def _structure_context(candidate: dict, ticker: dict) -> tuple[str, str, float]:
    score = float(candidate.get('score') or 0.0)
    persistence = int(candidate.get('persistence') or 0)
    trend = (candidate.get('trend') or candidate.get('status') or '').lower()
    momentum = float(candidate.get('momentum') or 0.0)
    drift_300s = float(ticker.get('drift_300s') or 0.0)
    drift_900s = float(ticker.get('drift_900s') or 0.0)
    freshness = float(ticker.get('freshness_seconds') or 9999.0)

    if freshness > FRESHNESS_LIMIT_SECONDS:
        return 'reject', 'stale_freshness', 0.0
    if drift_900s < STRUCTURE_MIN_DRIFT_900S:
        return 'reject', 'structure_downtrend', 0.0
    if trend in {'isolated spike', 'fading'}:
        return 'reject', f'structure_trend_block:{trend}', 0.0
    if persistence < ENTRY_MIN_PERSISTENCE:
        return 'reject', 'insufficient_persistence', 0.0

    structure_score = 0.0
    if drift_900s >= 0.12:
        structure_score += 1.0
    elif drift_900s >= 0.04:
        structure_score += 0.7
    else:
        structure_score += 0.35

    if persistence >= 5:
        structure_score += 0.7
    else:
        structure_score += 0.35

    if score >= 0.75:
        structure_score += 0.7
    elif score >= PULLBACK_RECLAIM_MIN_SCORE:
        structure_score += 0.4

    if momentum >= 4.0:
        structure_score += 0.4
    elif momentum >= 2.0:
        structure_score += 0.2

    if drift_300s < -0.20:
        return 'reject', 'drift_300_too_negative', structure_score
    if drift_300s > STRUCTURE_MAX_DRIFT_300S and momentum < 12.0:
        return 'reject', 'too_extended_for_entry', structure_score

    if drift_300s >= FULL_CONTINUATION_MIN_DRIFT_300S:
        return 'full', 'trend_supported_continuation', structure_score
    if drift_300s >= EARLY_RECLAIM_MIN_DRIFT_300S and drift_900s >= 0.0 and score >= PULLBACK_RECLAIM_MIN_SCORE:
        return 'early', 'early_reclaim_setup', structure_score
    if -0.02 <= drift_300s < EARLY_RECLAIM_MIN_DRIFT_300S and drift_900s >= 0.05 and score >= max(0.56, PULLBACK_RECLAIM_MIN_SCORE):
        return 'early', 'pullback_reclaim_setup', structure_score
    return 'reject', 'structure_not_reclaimed', structure_score


def _candidate_tier(candidate: dict, ticker: dict) -> tuple[str, str, float]:
    score = float(candidate.get('score') or 0.0)
    drift = float(ticker.get('drift_300s') or 0.0)
    drift_900s = float(ticker.get('drift_900s') or 0.0)
    momentum = float(candidate.get('momentum') or 0.0)
    persistence = int(candidate.get('persistence') or 0)

    structure_state, structure_reason, structure_score = _structure_context(candidate, ticker)
    if structure_state == 'reject':
        return '', structure_reason, structure_score
    if drift >= FAKE_PUMP_DRIFT_THRESHOLD and momentum < 12.0:
        return '', 'fake_pump_guard', structure_score
    if persistence == 4 and score < 0.56:
        return '', 'borderline_score_at_p4', structure_score

    high_confidence = score >= HIGH_CONFIDENCE_SCORE and persistence >= ENTRY_MIN_PERSISTENCE
    valid_setup = score >= ENTRY_MIN_SCORE and persistence >= ENTRY_MIN_PERSISTENCE

    if structure_state == 'full':
        if high_confidence and drift >= HIGH_CONFIDENCE_MIN_DRIFT_300S and drift_900s >= 0.02:
            return 'high', f'{structure_reason}:high_confidence_continuation', structure_score
        if high_confidence and drift >= -0.02 and drift_900s >= 0.08:
            return 'high', f'{structure_reason}:high_confidence_recovery', structure_score
        if valid_setup and drift >= ENTRY_MIN_DRIFT_300S and drift_900s >= 0.0:
            return 'standard', f'{structure_reason}:standard_continuation', structure_score
        if valid_setup and drift >= -0.02 and drift_900s >= 0.05:
            return 'standard', f'{structure_reason}:supported_flat_reclaim', structure_score

    if structure_state == 'early':
        if high_confidence and persistence >= 5:
            return 'standard', f'{structure_reason}:early_reclaim_high_confidence', structure_score
        if valid_setup and persistence >= 5 and score >= 0.50:
            return 'standard', f'{structure_reason}:early_reclaim_supported', structure_score
        if valid_setup and persistence >= 5 and drift >= -0.01 and drift_900s >= -0.30:
            return 'standard', f'{structure_reason}:weak_regime_flat_reclaim', structure_score

    return '', 'tier_filter_failed', structure_score


def _cooldown_blocked(symbol: str, state: dict, candidate: dict | None = None, ticker: dict | None = None) -> bool:
    entry = _get_symbol_state(state, symbol)
    blocked_until = _iso_to_dt(entry.get('reentry_blocked_until'))
    lifecycle = entry.get('lifecycle') or 'idle'
    now = datetime.now(timezone.utc)

    if blocked_until:
        if now >= blocked_until:
            entry['reentry_blocked_until'] = None
            blocked_until = None
        else:
            return True

    if lifecycle == 'active':
        return True
    if lifecycle in {'needs_reset', 'choppy', 'exhausted'}:
        last_entries = state.get('last_entries', {})
        dt = _iso_to_dt(last_entries.get(symbol))
        if not dt:
            return False
        elapsed_seconds = (now - dt).total_seconds()
        if elapsed_seconds >= COOLDOWN_MINUTES * 60:
            return False

        candidate = candidate or {}
        ticker = ticker or {}
        score = float(candidate.get('score') or 0.0)
        persistence = int(candidate.get('persistence') or 0)
        drift_300s = float(ticker.get('drift_300s') or 0.0)
        drift_900s = float(ticker.get('drift_900s') or 0.0)
        freshness = float(ticker.get('freshness_seconds') or 9999.0)

        materially_requalified = (
            score >= 0.75 and
            persistence >= 5 and
            freshness <= FRESHNESS_LIMIT_SECONDS and
            drift_300s >= 0.0 and
            drift_900s >= 0.0
        )
        if materially_requalified and elapsed_seconds >= 12 * 60:
            return False
        return True
    return False


def _normalized_guardrails(confidence: str | None = None) -> dict:
    return {
        'stop_loss_pct': STOP_LOSS_PCT,
        'profit_levels_pct': TRIM_LEVELS,
        'timeout_minutes': TIMEOUT_MINUTES,
        'trail_after_first_pct': TRAIL_AFTER_FIRST,
        'trail_after_second_pct': TRAIL_AFTER_SECOND,
        'confidence': confidence or 'standard',
    }


def _normalize_open_positions(open_positions: list[dict]) -> list[dict]:
    normalized = []
    for idx, position in enumerate(open_positions, start=1):
        confidence = position.get('confidence', 'standard')
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
        position['guardrails'] = _normalized_guardrails(confidence)
        normalized.append(position)
    return normalized


def _sync_symbol_state_with_positions(state: dict, open_positions: list[dict]) -> None:
    active_symbols = {(p.get('token') or '').upper() for p in open_positions if (p.get('token') or '').upper()}
    symbol_state = state.setdefault('symbol_state', {})
    for symbol, entry in symbol_state.items():
        upper_symbol = (symbol or '').upper()
        if upper_symbol in active_symbols:
            entry['lifecycle'] = 'active'
            continue
        if entry.get('lifecycle') == 'active':
            entry['lifecycle'] = 'idle'


def _build_shortlist(market_state: dict, tickers: dict, state: dict) -> list[dict]:
    candidates = []
    source_candidates = market_state.get('ranked_bench') or market_state.get('top_opportunities', [])
    for item in source_candidates[:CANDIDATE_BENCH_LIMIT]:
        symbol = (item.get('token') or '').upper()
        if not symbol:
            continue
        product_id = _symbol_to_product_id(symbol)
        ticker = tickers.get(product_id)
        if not ticker or ticker.get('price') is None:
            _append_jsonl(V2_CANDIDATE_EVALS_PATH, {
                'timestamp': _now_iso(),
                'token': symbol,
                'product_id': product_id,
                'decision': 'reject',
                'reason': 'missing_ticker_or_price',
            })
            continue
        candidate_payload = {
            'timestamp': _now_iso(),
            'token': symbol,
            'product_id': product_id,
            'score': float(item.get('score') or 0.0),
            'momentum': float(item.get('momentum') or 0.0),
            'persistence': int(item.get('persistence') or 0),
            'trend': item.get('trend') or item.get('status') or 'unknown',
            'price': float(ticker.get('price')),
            'drift_300s': float(ticker.get('drift_300s') or 0.0),
            'drift_900s': float(ticker.get('drift_900s') or 0.0),
            'freshness_seconds': float(ticker.get('freshness_seconds') or 0.0),
        }
        eligible, reentry_reason = _reentry_decision(symbol, state, item, ticker)
        if not eligible:
            _append_jsonl(V2_CANDIDATE_EVALS_PATH, {
                **candidate_payload,
                'decision': 'reject',
                'reason': reentry_reason or 'cooldown',
            })
            continue
        confidence, confidence_reason, structure_score = _candidate_tier(item, ticker)
        if not confidence:
            _append_jsonl(V2_CANDIDATE_EVALS_PATH, {
                **candidate_payload,
                'decision': 'reject',
                'reason': confidence_reason,
                'structure_score': round(structure_score, 3),
            })
            continue
        accepted_payload = {
            **candidate_payload,
            'decision': 'accept',
            'confidence_candidate': confidence,
            'confidence_reason': confidence_reason,
            'structure_score': round(structure_score, 3),
            'entry_reason': 'scanner_rank_plus_websocket_confirmation',
        }
        _append_jsonl(V2_CANDIDATE_EVALS_PATH, accepted_payload)
        candidates.append({
            'symbol': symbol,
            'product_id': product_id,
            'confidence': confidence,
            'score': accepted_payload['score'],
            'structure_score': accepted_payload['structure_score'],
            'momentum': accepted_payload['momentum'],
            'persistence': accepted_payload['persistence'],
            'trend': accepted_payload['trend'],
            'price': accepted_payload['price'],
            'drift_300s': accepted_payload['drift_300s'],
            'drift_900s': accepted_payload['drift_900s'],
            'freshness_seconds': accepted_payload['freshness_seconds'],
            'entry_reason': accepted_payload['entry_reason'],
        })
    candidates.sort(key=lambda x: (x.get('confidence') == 'high', x.get('structure_score', 0.0), x['score'], abs(x['drift_300s'])), reverse=True)
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


def _profit_profile() -> tuple[list[float], float, float]:
    return TRIM_LEVELS, TRAIL_AFTER_FIRST, TRAIL_AFTER_SECOND


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
        confidence = position.get('confidence', 'standard')
        timeout_limit = TIMEOUT_MINUTES
        stop_loss_pct = STOP_LOSS_PCT
        trim_levels, trail_first, trail_second = _profit_profile()
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
                    'confidence': confidence,
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
                'confidence': confidence,
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
        elif (
            highest_pnl >= EARLY_PROTECT_PNL_PCT
            and pnl_percent <= max(0.0, highest_pnl - EARLY_PROTECT_GIVEBACK_PCT)
            and drift_300s < 0
        ):
            exit_reason = 'early_profit_giveback'
            exit_category = 'EP'
        elif (
            time_in_trade_minutes >= FAILED_CONTINUATION_MINUTES
            and highest_pnl >= FAILED_CONTINUATION_PEAK_PCT
            and pnl_percent < FAILED_CONTINUATION_RETAIN_PCT
            and drift_300s < 0
        ):
            exit_reason = 'failed_continuation'
            exit_category = 'FC'
        elif (
            time_in_trade_minutes >= MODEST_CONTINUATION_MINUTES
            and highest_pnl >= MODEST_CONTINUATION_PEAK_PCT
            and pnl_percent <= MODEST_CONTINUATION_LOSS_PCT
            and drift_300s < -0.10
        ):
            exit_reason = 'modest_continuation_failure'
            exit_category = 'MCF'
        elif time_in_trade_minutes >= timeout_limit and pnl_percent <= 0:
            exit_reason = 'timeout'
            exit_category = 'TIME'
        elif time_in_trade_minutes >= NO_MOVE_MINUTES and highest_pnl < NO_MOVE_THRESHOLD_PCT and pnl_percent < NO_MOVE_THRESHOLD_PCT:
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
            lifecycle = 'leader_active'
            blocked_minutes = COOLDOWN_MINUTES
            if exit_reason in {'no_move', 'timeout'}:
                lifecycle = 'needs_reset'
                blocked_minutes = max(COOLDOWN_MINUTES, 35)
            elif exit_reason in {'failed_continuation', 'early_profit_giveback'}:
                lifecycle = 'choppy'
                blocked_minutes = max(COOLDOWN_MINUTES, 25)
            elif exit_reason in {'fake_pump_confirmed'}:
                lifecycle = 'exhausted'
                blocked_minutes = max(COOLDOWN_MINUTES, 45)
            elif exit_reason in {'trailing_exit'}:
                lifecycle = 'leader_active'
                blocked_minutes = 12
            elif exit_reason in {'stop_loss'}:
                lifecycle = 'needs_reset'
                blocked_minutes = max(COOLDOWN_MINUTES, 45)
            _set_symbol_reentry_state(
                state,
                position.get('token'),
                lifecycle=lifecycle,
                exit_reason=exit_reason,
                pnl_percent=round(pnl_percent, 4),
                highest_pnl=round(highest_pnl, 4),
                blocked_minutes=blocked_minutes,
            )
            exit_event = {
                'timestamp': _now_iso(),
                'action': 'close_position',
                'token': position.get('token'),
                'product_id': position.get('product_id'),
                'confidence': confidence,
                'entry_time': position.get('entry_time'),
                'time_in_trade_minutes': time_in_trade_minutes,
                'entry_price': entry_price,
                'current_price': current_price,
                'pnl_percent': round(pnl_percent, 4),
                'highest_pnl_percent': round(highest_pnl, 4),
                'drift_300s': drift_300s,
                'freshness_seconds': float(ticker.get('freshness_seconds') or 0.0),
                'move_character': move_character,
                'trim_step': trim_step,
                'trail_active': trail_active,
                'trail_distance_pct': active_trail,
                'remaining_size_pct': round(remaining_size_pct, 2),
                'exit_reason': exit_reason,
                'exit_category': exit_category,
                'stop_loss_pct': stop_loss_pct,
                'timeout_limit_minutes': timeout_limit,
                'no_move_minutes': NO_MOVE_MINUTES,
                'no_move_threshold_pct': NO_MOVE_THRESHOLD_PCT,
            }
            _append_jsonl(V2_DECISIONS_PATH, exit_event)
            _append_jsonl(V2_EXIT_EVENTS_PATH, exit_event)
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
            'confidence': candidate['confidence'],
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
            'guardrails': _normalized_guardrails(candidate['confidence']),
            'highest_pnl_percent': 0.0,
            'trim_step': 0,
            'trail_active': False,
            'trail_distance_pct': 0.0,
            'remaining_size_pct': 100.0,
            'de_risked_fake_pump': False,
        }
        new_positions.append(position)
        _mark_symbol_entry(state, candidate['symbol'])
        _append_jsonl(V2_DECISIONS_PATH, {
            'timestamp': now_iso,
            'action': 'open_position',
            'token': candidate['symbol'],
            'confidence': candidate['confidence'],
            'score': candidate['score'],
            'drift_300s': candidate['drift_300s'],
            'freshness_seconds': candidate['freshness_seconds'],
            'reason': candidate['entry_reason'],
        })
    return open_positions + new_positions, new_positions


def _log_position_snapshots(open_positions: list[dict]) -> None:
    timestamp = _now_iso()
    for position in open_positions:
        _append_jsonl(V2_POSITION_SNAPSHOTS_PATH, {
            'timestamp': timestamp,
            'token': position.get('token'),
            'product_id': position.get('product_id'),
            'confidence': position.get('confidence'),
            'trade_state': position.get('trade_state'),
            'move_character': position.get('move_character'),
            'entry_time': position.get('entry_time'),
            'last_update': position.get('last_update'),
            'entry_price': position.get('entry_price'),
            'current_price': position.get('current_price'),
            'pnl_percent': position.get('pnl_percent'),
            'highest_pnl_percent': position.get('highest_pnl_percent'),
            'time_in_trade_minutes': position.get('time_in_trade_minutes'),
            'scanner_score': position.get('scanner_score'),
            'momentum': position.get('momentum'),
            'persistence': position.get('persistence'),
            'trend': position.get('trend'),
            'websocket_drift_300s': position.get('websocket_drift_300s'),
            'websocket_freshness_seconds': position.get('websocket_freshness_seconds'),
            'trim_step': position.get('trim_step'),
            'trail_active': position.get('trail_active'),
            'trail_distance_pct': position.get('trail_distance_pct'),
            'remaining_size_pct': position.get('remaining_size_pct'),
            'de_risked_fake_pump': position.get('de_risked_fake_pump'),
        })


def _build_funnel_summary(market_state: dict, eval_lines: list[dict], shortlist: list[dict], new_positions: list[dict], ws_state: dict) -> dict:
    reject_reasons: dict[str, int] = {}
    for row in eval_lines:
        if row.get('decision') == 'reject':
            reason = str(row.get('reason') or 'unknown')
            reject_reasons[reason] = reject_reasons.get(reason, 0) + 1
    return {
        'timestamp': _now_iso(),
        'websocket_connected': bool(ws_state.get('connected')),
        'scanner_signal_count': len(market_state.get('top_opportunities', []) or []),
        'scanner_tokens': [str(item.get('token') or '').upper() for item in (market_state.get('top_opportunities') or [])],
        'candidate_eval_count': len(eval_lines),
        'accepted_candidate_count': sum(1 for row in eval_lines if row.get('decision') == 'accept'),
        'rejected_candidate_count': sum(1 for row in eval_lines if row.get('decision') == 'reject'),
        'reject_reasons': reject_reasons,
        'shortlist_count': len(shortlist),
        'shortlist_tokens': [c.get('symbol') for c in shortlist],
        'new_positions_count': len(new_positions),
        'new_position_tokens': [p.get('token') for p in new_positions],
    }


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
    _sync_symbol_state_with_positions(state, open_positions)
    trades_log = _load_json(V2_TRADES_LOG_PATH, [])
    prior_eval_lines = 0
    if V2_CANDIDATE_EVALS_PATH.exists():
        try:
            prior_eval_lines = len(V2_CANDIDATE_EVALS_PATH.read_text(encoding='utf-8').splitlines())
        except Exception:
            prior_eval_lines = 0

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
        'high_confidence_candidates': sum(1 for c in shortlist if c.get('confidence') == 'high'),
        'standard_confidence_candidates': sum(1 for c in shortlist if c.get('confidence') == 'standard'),
        'websocket_connected': bool(ws_state.get('connected')),
        'top_candidates': shortlist[:5],
    }

    _log_position_snapshots(updated_positions)
    audit_summary = _build_audit_summary(updated_positions, trades_log, summary)
    eval_lines = []
    if V2_CANDIDATE_EVALS_PATH.exists():
        try:
            all_lines = V2_CANDIDATE_EVALS_PATH.read_text(encoding='utf-8').splitlines()
            eval_lines = [json.loads(line) for line in all_lines[prior_eval_lines:] if line.strip()]
        except Exception:
            eval_lines = []
    funnel_summary = _build_funnel_summary(market_state, eval_lines, shortlist, new_positions, ws_state)

    _write_json(V2_OPEN_POSITIONS_PATH, updated_positions)
    _write_json(V2_TRADES_LOG_PATH, trades_log)
    _write_json(V2_STATE_PATH, state)
    _write_json(V2_AUDIT_SUMMARY_PATH, audit_summary)
    _write_json(V2_FUNNEL_SUMMARY_PATH, funnel_summary)

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
        'funnel_summary': funnel_summary,
    }


if __name__ == '__main__':
    print(json.dumps(paper_trader_v2(), indent=2))
