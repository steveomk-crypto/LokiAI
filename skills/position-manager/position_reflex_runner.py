from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE = Path('/home/lokiai/.openclaw/workspace')
OPEN_POSITIONS_PATH = WORKSPACE / 'paper_trades' / 'open_positions_v2.json'
TICKERS_PATH = WORKSPACE / 'cache' / 'coinbase_tickers.json'
REFLEX_LOG_PATH = WORKSPACE / 'paper_trades' / 'v2_position_reflex_actions.jsonl'

EARLY_WINDOW_MINUTES = 8
BURST_ENTRY_DRIFT_300S = 0.45
BURST_ENTRY_SCANNER_SCORE = 0.52
NO_EXPANSION_AFTER_MINUTES = 2
NO_EXPANSION_MAX_HIGH_PNL = 0.12
COLLAPSE_DRIFT_THRESHOLD = -0.08
STALE_FRESHNESS_SECONDS = 75
DE_RISK_REMAINING_PCT = 75.0


def _load_json(path: Path, default: Any):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _save_json(path: Path, payload: Any) -> None:
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


def _minutes_since(value: str | None, now: datetime) -> float:
    dt = _iso_to_dt(value)
    if not dt:
        return float('inf')
    return (now - dt).total_seconds() / 60.0


def _compute_pnl(entry_price: float, current_price: float) -> float:
    if entry_price <= 0:
        return 0.0
    return ((current_price - entry_price) / entry_price) * 100.0


def _is_early_trade(position: dict, now: datetime) -> bool:
    return _minutes_since(position.get('entry_time'), now) <= EARLY_WINDOW_MINUTES


def _is_burst_entry(position: dict) -> bool:
    entry_drift = float(position.get('entry_drift_300s') or position.get('websocket_drift_300s') or 0.0)
    scanner_score = float(position.get('scanner_score') or 0.0)
    confidence = str(position.get('confidence') or '').lower()
    return (
        entry_drift >= BURST_ENTRY_DRIFT_300S
        or scanner_score >= BURST_ENTRY_SCANNER_SCORE
        or confidence == 'high'
    )


def _classify_reflex(position: dict, ticker: dict, now: datetime) -> tuple[str, str]:
    if not _is_early_trade(position, now):
        return 'HOLD', 'outside_reflex_window'
    if not _is_burst_entry(position):
        return 'HOLD', 'non_burst_entry'

    entry_price = float(position.get('entry_price') or 0.0)
    current_price = float(ticker.get('price') or position.get('current_price') or entry_price)
    pnl = _compute_pnl(entry_price, current_price)
    highest_pnl = max(float(position.get('highest_pnl_percent') or 0.0), pnl)
    drift_300s = float(ticker.get('drift_300s') or position.get('websocket_drift_300s') or 0.0)
    freshness = float(ticker.get('freshness_seconds') or position.get('websocket_freshness_seconds') or 9999.0)
    minutes_open = _minutes_since(position.get('entry_time'), now)

    if minutes_open >= NO_EXPANSION_AFTER_MINUTES and highest_pnl <= NO_EXPANSION_MAX_HIGH_PNL and drift_300s <= 0.03:
        return 'MARK_AT_RISK', 'burst_failed_to_expand'

    if drift_300s <= COLLAPSE_DRIFT_THRESHOLD and pnl <= 0.0:
        return 'DE_RISK', 'drift_collapse_after_entry'

    if freshness >= STALE_FRESHNESS_SECONDS and highest_pnl <= NO_EXPANSION_MAX_HIGH_PNL:
        return 'MARK_AT_RISK', 'stale_no_followthrough'

    return 'HOLD', 'continuation_still_possible'


def position_reflex_runner() -> list[dict[str, Any]]:
    open_positions = _load_json(OPEN_POSITIONS_PATH, [])
    if not open_positions:
        return []

    tickers = _load_json(TICKERS_PATH, {})
    now = datetime.now(timezone.utc)
    timestamp = _now_iso()
    actions: list[dict[str, Any]] = []
    updated_positions: list[dict[str, Any]] = []

    for position in open_positions:
        token = str(position.get('token') or '').upper()
        product_id = position.get('product_id') or (f'{token}-USD' if token else None)
        ticker = tickers.get(product_id) if isinstance(product_id, str) else None
        if not isinstance(ticker, dict):
            updated_positions.append(position)
            continue

        action, reason = _classify_reflex(position, ticker, now)
        current_price = float(ticker.get('price') or position.get('current_price') or position.get('entry_price') or 0.0)
        pnl = _compute_pnl(float(position.get('entry_price') or 0.0), current_price)
        highest_pnl = max(float(position.get('highest_pnl_percent') or 0.0), pnl)
        current_drift = float(ticker.get('drift_300s') or 0.0)
        current_freshness = float(ticker.get('freshness_seconds') or 9999.0)
        time_in_trade_minutes = int(_minutes_since(position.get('entry_time'), now))

        trade_state_before = position.get('trade_state', 'ACTIVE')
        move_character_before = position.get('move_character', 'building')
        trade_state_after = trade_state_before
        move_character_after = move_character_before

        if action == 'MARK_AT_RISK' and trade_state_before == 'ACTIVE':
            trade_state_after = 'AT_RISK'
            move_character_after = 'stalling'
        elif action == 'DE_RISK':
            trade_state_after = 'DE_RISKED'
            move_character_after = 'fading'
            position['remaining_size_pct'] = min(float(position.get('remaining_size_pct') or 100.0), DE_RISK_REMAINING_PCT)
            position['de_risked_fake_pump'] = True

        position['current_price'] = current_price
        position['pnl_percent'] = round(pnl, 4)
        position['highest_pnl_percent'] = round(highest_pnl, 4)
        position['time_in_trade_minutes'] = max(time_in_trade_minutes, 0)
        position['websocket_drift_300s'] = current_drift
        position['websocket_freshness_seconds'] = current_freshness
        position['trade_state'] = trade_state_after
        position['move_character'] = move_character_after
        position['last_update'] = timestamp
        position['reflex_flags'] = sorted(set(list(position.get('reflex_flags') or []) + ([] if action == 'HOLD' else [reason])))
        position['reflex_last_action'] = action
        position['reflex_last_reason'] = reason
        position['reflex_last_timestamp'] = timestamp

        log_row = {
            'timestamp': timestamp,
            'token': token,
            'product_id': product_id,
            'action': action,
            'reason': reason,
            'trade_state_before': trade_state_before,
            'trade_state_after': trade_state_after,
            'move_character_before': move_character_before,
            'move_character_after': move_character_after,
            'entry_time': position.get('entry_time'),
            'time_in_trade_minutes': max(time_in_trade_minutes, 0),
            'entry_price': float(position.get('entry_price') or 0.0),
            'current_price': current_price,
            'pnl_percent': round(pnl, 4),
            'highest_pnl_percent': round(highest_pnl, 4),
            'entry_drift_300s': float(position.get('entry_drift_300s') or position.get('websocket_drift_300s') or 0.0),
            'current_drift_300s': current_drift,
            'entry_freshness_seconds': float(position.get('entry_freshness_seconds') or position.get('websocket_freshness_seconds') or 0.0),
            'current_freshness_seconds': current_freshness,
            'confidence': position.get('confidence'),
            'scanner_score': float(position.get('scanner_score') or 0.0),
        }
        _append_jsonl(REFLEX_LOG_PATH, log_row)
        if action != 'HOLD':
            actions.append(log_row)
        updated_positions.append(position)

    _save_json(OPEN_POSITIONS_PATH, updated_positions)
    return actions


if __name__ == '__main__':
    result = position_reflex_runner()
    print(json.dumps(result, indent=2))
