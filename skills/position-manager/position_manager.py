import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from atr_utils import get_atr_for_symbol, ATR_REFRESH_MINUTES

OPEN_POSITIONS_PATH = Path("/home/lokiai/.openclaw/workspace/paper_trades/open_positions_v2.json")
TRADES_LOG_PATH = Path("/home/lokiai/.openclaw/workspace/paper_trades/trades_log_v2.json")
POSITION_ACTION_LOG = Path("/home/lokiai/.openclaw/workspace/paper_trades/position_actions_v2.json")
CLOSE_REPORT_PATH = Path("/home/lokiai/.openclaw/workspace/paper_trades/v2_exit_events.jsonl")
ALERT_LOG_PATH = Path("/home/lokiai/.openclaw/workspace/system_logs/pipeline_alerts.jsonl")

TRAIL_BREAK_EVEN = 3.0
TRAIL_PLUS_THREE = 5.0
TRAIL_TARGET = 2.0
TRAIL_ARM_PCT = 5.0
PARTIAL_FIRST_PCT = 3.0
PARTIAL_SECOND_PCT = 6.0
PARTIAL_REDUCTION = 0.5
LOSER_CUTOFF = -3.0
NO_MOVEMENT_THRESHOLD = 0.5
TIME_DECAY_HOURS = 3.5
TRAILING_GAP_PCT = 3.0
TIGHT_TRAILING_GAP_PCT = 2.0

TIER_BEHAVIOR = {
    'A': {
        'partial_rules': [
            {'flag': 'tier_a_trim_30', 'threshold': 6.0, 'reduction': 0.3, 'label': 'Tier A trim 30% at +6%'},
            {'flag': 'tier_a_trim_20', 'threshold': 10.0, 'reduction': 0.2, 'label': 'Tier A trim 20% at +10%'}
        ],
        'trail_arm_pct': 6.0,
        'trail_gap_pct': 3.0,
        'tight_trail_trigger_pct': 10.0,
        'tight_trail_gap_pct': 2.0,
        'floor_pct': 2.0,
        'break_even_pct': 6.0,
        'atr_multiplier': 2.0
    },
    'B': {
        'partial_rules': [
            {'flag': 'tier_b_trim_first', 'threshold': 4.0, 'reduction': 0.25, 'label': 'Tier B trim 25% at +4%'},
            {'flag': 'tier_b_trim_second', 'threshold': 8.0, 'reduction': 0.25, 'label': 'Tier B trim 25% at +8%'}
        ],
        'trail_arm_pct': 5.0,
        'trail_gap_pct': 2.0,
        'tight_trail_trigger_pct': None,
        'tight_trail_gap_pct': 2.0,
        'floor_pct': 1.0,
        'break_even_pct': None,
        'atr_multiplier': 1.5
    }
}


def _load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            return default
    return default


def _save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding='utf-8')


def _append_action(entry: Dict):
    logs = _load_json(POSITION_ACTION_LOG, [])
    logs.append(entry)
    _save_json(POSITION_ACTION_LOG, logs)


def _append_trade_log(entry: Dict):
    trades = _load_json(TRADES_LOG_PATH, [])
    trades.append(entry)
    _save_json(TRADES_LOG_PATH, trades)


def _minutes_since(timestamp: str, now: datetime) -> float:
    if not timestamp:
        return float('inf')
    try:
        ts = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return float('inf')
    return (now - ts).total_seconds() / 60.0


def _append_close_event(entry: Dict):
    CLOSE_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CLOSE_REPORT_PATH, 'a') as handle:
        handle.write(json.dumps(entry) + '\n')


def _append_alert(entry: Dict):
    ALERT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(ALERT_LOG_PATH, 'a') as handle:
        handle.write(json.dumps(entry) + '\n')


def _time_in_trade_hours(entry_time: str, now: datetime) -> float:
    try:
        start = datetime.fromisoformat(entry_time.replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return 0.0
    delta = now - start
    return delta.total_seconds() / 3600.0


def _compute_pnl(entry_price: float, current_price: float) -> float:
    if not entry_price:
        return 0.0
    return ((current_price - entry_price) / entry_price) * 100.0


def position_manager():
    open_positions = _load_json(OPEN_POSITIONS_PATH, [])
    if not open_positions:
        return []

    now = datetime.now(timezone.utc)
    updated_positions: List[Dict] = []
    actions: List[Dict] = []

    for position in open_positions:
        token = position.get('token') or 'UNKNOWN'
        entry_price = float(position.get('entry_price') or 0)
        current_price = float(position.get('current_price') or entry_price)
        stop_price = float(position.get('stop_price') or entry_price)
        position_size = float(position.get('position_size_usd') or 0)
        entry_time = position.get('entry_time')
        pnl_pct = _compute_pnl(entry_price, current_price)
        hours_open = _time_in_trade_hours(entry_time, now)
        tier = (position.get('tier') or 'A').upper()
        tier_cfg = TIER_BEHAVIOR.get(tier, TIER_BEHAVIOR['A'])
        atr_usd = float(position.get('atr_usd') or 0.0)
        atr_meta = {'id': position.get('coin_id')}
        move_character = str(position.get('move_character') or '').lower()
        if atr_usd <= 0 or _minutes_since(position.get('atr_last_updated'), now) > ATR_REFRESH_MINUTES:
            atr_info = get_atr_for_symbol(token, atr_meta)
            if atr_info:
                atr_usd = atr_info['atr_usd']
                position['atr_usd'] = atr_info['atr_usd']
                position['atr_pct'] = atr_info['atr_pct']
                position['atr_last_updated'] = atr_info['fetched_at']
                position['atr_source'] = atr_info['source']

        action = 'HOLD'
        reason = 'Within plan'

        guardrails = position.get('guardrails') or {}
        loser_cutoff = float(position.get('max_loss_pct') or guardrails.get('stop_loss_pct') or LOSER_CUTOFF)
        timeout_minutes = float(guardrails.get('timeout_minutes') or (float(position.get('custom_time_stop_hours') or TIME_DECAY_HOURS) * 60.0))
        time_stop_hours = timeout_minutes / 60.0
        no_move_threshold = float(position.get('custom_no_movement_pct') or NO_MOVEMENT_THRESHOLD)
        profit_levels = [float(x) for x in (guardrails.get('profit_levels_pct') or [])] or [rule['threshold'] for rule in tier_cfg.get('partial_rules', [])]
        trail_after_first = float(guardrails.get('trail_after_first_pct') or tier_cfg.get('floor_pct') or 0.0)
        trail_after_second = float(guardrails.get('trail_after_second_pct') or tier_cfg.get('tight_trail_gap_pct') or trail_after_first)

        # Loser control
        if pnl_pct <= loser_cutoff:
            action = 'CLOSE'
            reason = f'Loser control triggered ({pnl_pct:.2f}%)'
        # Time decay
        elif hours_open >= time_stop_hours and pnl_pct < no_move_threshold:
            action = 'CLOSE'
            reason = f'Time stop: <{no_move_threshold:.2f}% after {time_stop_hours}h'
        else:
            # Trailing stop logic if activated
            if position.get('trail_active'):
                trail_high = max(position.get('trail_high', current_price), current_price)
                position['trail_high'] = trail_high
                gap_pct = tier_cfg.get('trail_gap_pct', TRAILING_GAP_PCT)
                tight_trigger = tier_cfg.get('tight_trail_trigger_pct')
                if tight_trigger and pnl_pct >= tight_trigger:
                    gap_pct = tier_cfg.get('tight_trail_gap_pct', gap_pct)
                atr_multiplier = tier_cfg.get('atr_multiplier', 2.0 if tier == 'A' else 1.5)
                desired_trail = None
                if atr_usd > 0:
                    desired_trail = trail_high - (atr_usd * atr_multiplier)
                else:
                    desired_trail = trail_high * (1 - gap_pct / 100)
                floor_pct = tier_cfg.get('floor_pct')
                if floor_pct is not None:
                    floor_price = entry_price * (1 + floor_pct / 100)
                    desired_trail = max(desired_trail, floor_price)
                if desired_trail > stop_price:
                    stop_price = desired_trail
                if current_price <= stop_price:
                    action = 'CLOSE'
                    reason = f'Trailing stop exit ({tier} {pnl_pct:.2f}%)'
            if action == 'HOLD':
                partial_triggered = False
                for idx, threshold in enumerate(profit_levels, start=1):
                    flag_field = f"partial_profit_level_{idx}_hit"
                    if position.get(flag_field):
                        continue
                    if pnl_pct >= threshold:
                        action = 'PARTIAL_CLOSE'
                        reason = f'Guardrail trim {idx} at +{threshold:.2f}%'
                        portion = 0.25 if idx < len(profit_levels) else 0.15
                        new_size = round(position_size * (1 - portion), 2)
                        position['position_size_usd'] = new_size
                        position[flag_field] = True
                        position['trail_active'] = True
                        position['trail_high'] = current_price
                        floor_pct = trail_after_first if idx == 1 else trail_after_second
                        desired_trail = entry_price * (1 + floor_pct / 100) if floor_pct else stop_price
                        stop_price = max(stop_price, desired_trail)
                        _append_close_event({
                            'timestamp': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
                            'token': token,
                            'event': 'partial_take_profit',
                            'portion': portion,
                            'pnl_percent': round(pnl_pct, 4),
                            'tier': tier
                        })
                        position_size = new_size
                        partial_triggered = True
                        break
                if action == 'PARTIAL_CLOSE':
                    pass
                elif move_character in {'fake_pump', 'stalling', 'fading'} and pnl_pct > 0 and not position.get('de_risked_fake_pump'):
                    action = 'TRAIL_ARM'
                    reason = f'De-risk {move_character} move'
                    position['trail_active'] = True
                    position['trail_high'] = current_price
                    stop_floor = entry_price * (1 + trail_after_first / 100) if trail_after_first else entry_price
                    stop_price = max(stop_price, stop_floor)
                    position['de_risked_fake_pump'] = True
                elif not position.get('trail_active') and profit_levels and pnl_pct >= profit_levels[0]:
                    action = 'TRAIL_ARM'
                    reason = f'Trail armed ({tier} @ {pnl_pct:.2f}%)'
                    position['trail_active'] = True
                    position['trail_high'] = current_price
                    stop_floor = entry_price * (1 + trail_after_first / 100) if trail_after_first else entry_price
                    stop_price = max(stop_price, stop_floor)

        action_entry = {
            'timestamp': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'token': token,
            'action': action,
            'reason': reason,
            'pnl_percent': round(pnl_pct, 4),
            'hours_open': round(hours_open, 2),
            'stop_price': round(stop_price, 6),
            'position_size_usd': position_size,
            'tier': tier
        }

        if action == 'CLOSE':
            close_category = 'OTHER'
            close_event_type = 'full_exit'
            if 'Take profit' in reason:
                close_category = 'TP'
            elif 'Trailing stop' in reason:
                close_category = 'TP'
                close_event_type = 'trailing_stop_exit'
            elif 'Loser control' in reason:
                close_category = 'SL'
            elif 'Time stop' in reason:
                close_category = 'TIME'
            trade_record = position.copy()
            trade_record['status'] = 'closed'
            trade_record['exit_price'] = current_price
            trade_record['exit_time'] = now.strftime('%Y-%m-%dT%H:%M:%SZ')
            trade_record['exit_reason'] = reason
            trade_record['exit_category'] = close_category
            trade_record['pnl_percent'] = round(pnl_pct, 4)
            trade_record['pnl_usd'] = round(position_size * (pnl_pct / 100.0), 4)
            _append_trade_log(trade_record)
            if close_category:
                close_event = {
                    'timestamp': trade_record['exit_time'],
                    'token': token,
                    'event': close_event_type,
                    'category': close_category,
                    'pnl_percent': trade_record['pnl_percent']
                }
                _append_close_event(close_event)
            should_alert = (
                close_category in ('SL', 'TIME') or
                'loser control' in reason.lower() or
                'manual_trim' in reason.lower()
            )
            if should_alert:
                _append_alert({
                    'timestamp': trade_record['exit_time'],
                    'token': token,
                    'reason': reason,
                    'category': close_category,
                    'pnl_percent': trade_record['pnl_percent'],
                    'hours_open': hours_open
                })
            action_entry['position_size_usd'] = 0.0
            action_entry['category'] = close_category
        elif action == 'PARTIAL_CLOSE':
            position['partial_taken'] = True
            position['stop_price'] = round(stop_price, 6)
            action_entry['position_size_usd'] = position['position_size_usd']
            updated_positions.append(position)
        else:
            if action in ('TRAIL_STOP', 'TRAIL_ARM'):
                position['stop_price'] = round(stop_price, 6)
            updated_positions.append(position)

        _append_action(action_entry)
        if action != 'HOLD':
            actions.append({'token': token, 'action': action, 'reason': reason, 'category': action_entry.get('category')})

    _save_json(OPEN_POSITIONS_PATH, updated_positions)
    return actions


if __name__ == '__main__':
    result = position_manager()
    print(json.dumps(result, indent=2))
