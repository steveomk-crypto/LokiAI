import json
import os
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Dict, List, Optional
from urllib import error, parse, request

from api_usage import log_api_call
from scripts.telegram_lanes import resolve_lane_target

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

API_URL_TEMPLATE = "https://api.telegram.org/bot{token}/sendMessage"
WORKSPACE = Path("/home/lokiai/.openclaw/workspace")
OPEN_POSITIONS_PATH = WORKSPACE / "paper_trades" / "open_positions.json"
TRADES_LOG_PATH = WORKSPACE / "paper_trades" / "trades_log.json"
MARKET_LOGS_DIR = WORKSPACE / "market_logs"
AUTONOMOUS_LOG_PATH = WORKSPACE / "system_logs" / "autonomous_market_loop.log"
ALERT_LOG_PATH = WORKSPACE / "system_logs" / "pipeline_alerts.jsonl"
STATE_PATH = WORKSPACE / "cache" / "telegram_status_state.json"
TIER_B_GUARD_PATH = WORKSPACE / "paper_trades" / "tier_b_guard_state.json"
MARKET_STATE_PATH = WORKSPACE / "cache" / "market_state.json"
SESSION_GUARD_PATH = WORKSPACE / "cache" / "session_guard.json"
RUN_STATE_PATH = WORKSPACE / "run_state.json"
LOCAL_TZ = ZoneInfo("Asia/Kuala_Lumpur") if ZoneInfo else timezone.utc
MAX_TELEGRAM_LENGTH = 3900
TOP_MOVER_LIMIT = 3
MODE_DESCRIPTIONS = {
    'baseline': 'Tier A $100×2 | Tier B $25×5',
    'high_opportunity': 'Tier A $120×3 | Tier B $40×6'
}
ACTIVE_POSITION_LIMIT = 8
TRADE_EXIT_LIMIT = 5
BINANCE_DEPTH_URL = "https://api.binance.com/api/v3/depth"
BINANCE_TRADES_URL = "https://api.binance.com/api/v3/trades"
HEALTH_TASK_LIMIT = 32
HEALTH_LOG_WINDOW = 400


def _get_env_var(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Environment variable {name} is not set")
    return value


def _load_json_list(path: Path) -> List[Dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _load_json_dict(path: Path) -> Dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _load_market_state_snapshot() -> Dict:
    return _load_json_dict(MARKET_STATE_PATH)


def _load_run_baseline():
    if not RUN_STATE_PATH.exists():
        return None, None
    try:
        payload = json.loads(RUN_STATE_PATH.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return None, None
    baseline = payload.get('run_id')
    if not baseline:
        return None, None
    dt_str = baseline[:-1] + '+00:00' if baseline.endswith('Z') else baseline
    try:
        dt_obj = datetime.fromisoformat(dt_str)
    except ValueError:
        return baseline, None
    return baseline, dt_obj


def _load_session_guard_snapshot() -> Dict:
    return _load_json_dict(SESSION_GUARD_PATH)


def _parse_dt(value: str):
    if not value or not isinstance(value, str):
        return None
    value = value.strip()
    if value.endswith('Z'):
        value = value[:-1] + '+00:00'
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _format_dt(value: str, fmt: str = "%H:%M") -> str:
    dt_obj = _parse_dt(value)
    if not dt_obj:
        return "?"
    if dt_obj.tzinfo is None:
        dt_obj = dt_obj.replace(tzinfo=timezone.utc)
    target_tz = LOCAL_TZ or timezone.utc
    return dt_obj.astimezone(target_tz).strftime(fmt)


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _format_usd(value: float, show_sign: bool = False) -> str:
    prefix = ""
    abs_val = abs(value)
    if abs_val >= 1_000_000_000:
        formatted = f"${abs_val/1_000_000_000:.1f}B"
    elif abs_val >= 1_000_000:
        formatted = f"${abs_val/1_000_000:.1f}M"
    elif abs_val >= 1_000:
        formatted = f"${abs_val/1_000:.1f}K"
    else:
        formatted = f"${abs_val:,.2f}"
    if show_sign and value != 0:
        prefix = "+" if value > 0 else "-"
    elif show_sign and value == 0:
        prefix = "±"
    elif not show_sign and value < 0:
        prefix = "-"
    return f"{prefix}{formatted}"


def _format_delta(current, previous, value_type: str):
    if previous is None:
        return "–"
    diff = current - previous
    if value_type == 'count':
        if diff == 0:
            return "0"
        sign = '+' if diff > 0 else '−'
        return f"{sign}{abs(diff)}"
    if value_type == 'percent':
        if abs(diff) < 0.1:
            return "0.0%"
        sign = '+' if diff > 0 else '−'
        return f"{sign}{abs(diff):.1f}%"
    if value_type == 'usd':
        if abs(diff) < 0.01:
            return "$0"
        sign = '+' if diff > 0 else '−'
        return f"{sign}{_format_usd(abs(diff), show_sign=False)}"
    return "–"


def _load_top_movers(limit: int = TOP_MOVER_LIMIT) -> List[Dict]:
    if not MARKET_LOGS_DIR.exists():
        return []
    files = sorted(MARKET_LOGS_DIR.glob("*.jsonl"))
    if not files:
        return []
    latest_file = files[-1]
    latest_entries: List[Dict] = []
    latest_ts = None
    try:
        with latest_file.open('r', encoding='utf-8') as handle:
            for raw in handle:
                line = raw.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = entry.get('timestamp')
                if not ts:
                    continue
                if latest_ts is None or ts > latest_ts:
                    latest_ts = ts
                    latest_entries = [entry]
                elif ts == latest_ts:
                    latest_entries.append(entry)
    except FileNotFoundError:
        return []

    movers = sorted(
        latest_entries,
        key=lambda e: _safe_float(e.get('score')),
        reverse=True
    )[:limit]
    formatted = []
    for entry in movers:
        formatted.append({
            'token': entry.get('token') or '?',
            'momentum': _safe_float(entry.get('momentum')),
            'volume': _safe_float(entry.get('volume')),
            'trend': entry.get('momentum_trend') or entry.get('trend') or entry.get('status') or 'n/a',
            'score': _safe_float(entry.get('score')),
        })
    return formatted


def _load_loop_health() -> str:
    if not AUTONOMOUS_LOG_PATH.exists():
        return "unknown (no log)"
    recent = deque(maxlen=HEALTH_LOG_WINDOW)
    with AUTONOMOUS_LOG_PATH.open('r', encoding='utf-8') as handle:
        for raw in handle:
            line = raw.strip()
            if line:
                recent.append(line)

    seen_tasks = set()
    latest_entries = []
    for raw in reversed(recent):
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            continue
        task = entry.get('task')
        if not task or task in seen_tasks:
            continue
        seen_tasks.add(task)
        latest_entries.append(entry)
        if len(latest_entries) >= HEALTH_TASK_LIMIT:
            break

    last_success_ts = _load_last_success_timestamp()
    for entry in latest_entries:
        status = entry.get('status', 'ok')
        if status in ('ok', 'success'):
            continue
        task = entry.get('task', 'unknown')
        if task == 'telegram_sender' and last_success_ts:
            entry_ts = _parse_dt(entry.get('timestamp'))
            if entry_ts and entry_ts <= last_success_ts:
                continue
        return f"Issue: {task} → {status}"
    return "OK"


def _format_trade_exits(trades: List[Dict]) -> str:
    if not trades:
        return "No trade exits this cycle."
    lines = []
    for trade in trades[:TRADE_EXIT_LIMIT]:
        token = trade.get('token', '?')
        pnl = _safe_float(trade.get('pnl_percent'))
        reason = trade.get('exit_reason') or trade.get('exit_category') or 'exit'
        when = _format_dt(trade.get('exit_time'))
        lines.append(f"- {token} {pnl:+.2f}% — *{reason} @ {when}*")
    remaining = len(trades) - TRADE_EXIT_LIMIT
    if remaining > 0:
        lines.append(f"… +{remaining} more exits")
    return "\n".join(lines)


def _format_position_deltas(entries: List[str], exits: List[str]) -> str:
    if not entries and not exits:
        return "Positions unchanged."
    parts = []
    if entries:
        parts.append(f"Entries: {', '.join(entries)}")
    if exits:
        parts.append(f"Exits: {', '.join(exits)}")
    return "; ".join(parts)


def _format_top_movers(movers: List[Dict]) -> str:
    if not movers:
        return "No fresh scanner signals."
    lines = []
    for mover in movers:
        lines.append(
            f"- {mover['token']} momentum {mover['momentum']:+.1f}% | "
            f"{_format_usd(mover['volume'])} vol | {mover['trend']} | score {mover['score']:.2f}"
        )
    return "\n".join(lines)


def _format_last_closed(closed: List[Dict]) -> str:
    if not closed:
        return "No closed trades yet."
    lines = []
    for trade in closed[:3]:
        token = trade.get('token', '?')
        pnl = _safe_float(trade.get('pnl_percent'))
        reason = trade.get('exit_reason') or trade.get('exit_category') or trade.get('status', 'n/a')
        exit_time = _format_dt(trade.get('exit_time') or trade.get('last_updated'))
        lines.append(f"- {token} {pnl:+.2f}% ({reason}) @ {exit_time}")
    return "\n".join(lines)


def _format_active_positions(open_positions: List[Dict]) -> str:
    if not open_positions:
        return "No active positions."
    portions = []
    for pos in open_positions[:ACTIVE_POSITION_LIMIT]:
        token = pos.get('token', '?')
        pnl = _safe_float(pos.get('pnl_percent'))
        entry_time = _format_dt(pos.get('entry_time') or pos.get('signal_timestamp'), fmt="%H:%M")
        portions.append(f"{token} {pnl:+.2f}% (entry {entry_time})")
    remaining = len(open_positions) - ACTIVE_POSITION_LIMIT
    if remaining > 0:
        portions.append(f"… +{remaining} more")
    return ", ".join(portions)


def _format_mode_line(snapshot: Dict) -> str:
    mode = str(snapshot.get('mode') or 'baseline').lower()
    label = ' '.join(word.capitalize() for word in mode.split('_'))
    desc = MODE_DESCRIPTIONS.get(mode, 'Tier sizing default')
    return f"Mode: {label} ({desc})"


def _format_guard_line(snapshot: Dict) -> str:
    if not snapshot:
        return "Session guard: n/a"
    net = _format_usd(snapshot.get('net_pnl') or 0.0, show_sign=True)
    threshold = _format_usd(snapshot.get('threshold') or 0.0, show_sign=True)
    if snapshot.get('kill_switch'):
        cooldown = snapshot.get('cooldown_runs', 0)
        return f"Session guard: HALTED (net {net} / limit {threshold}, cooldown {cooldown})"
    return f"Session guard: OK (net {net} / limit {threshold})"


def _load_tier_b_guard() -> Dict:
    if not TIER_B_GUARD_PATH.exists():
        return {'session_start': None, 'realized_pnl': 0.0, 'paused': False}
    try:
        payload = json.loads(TIER_B_GUARD_PATH.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        payload = {}
    return {
        'session_start': payload.get('session_start'),
        'realized_pnl': _safe_float(payload.get('realized_pnl')),
        'unrealized_pnl': _safe_float(payload.get('unrealized_pnl')),
        'net_pnl': _safe_float(payload.get('net_pnl')),
        'paused': bool(payload.get('paused'))
    }


def _init_tier_bucket():
    return {'open': 0, 'closed': 0, 'realized': 0.0, 'unrealized': 0.0}


def _summarize_by_tier(open_positions: List[Dict], trades: List[Dict]) -> Dict[str, Dict]:
    stats = {'A': _init_tier_bucket(), 'B': _init_tier_bucket()}
    for position in open_positions:
        tier = str(position.get('tier') or 'A').upper()
        stats.setdefault(tier, _init_tier_bucket())
        size = _safe_float(position.get('position_size_usd'))
        pnl = _safe_float(position.get('pnl_percent'))
        stats[tier]['open'] += 1
        stats[tier]['unrealized'] += size * pnl / 100.0
    for trade in trades:
        if str(trade.get('status', '')).lower() != 'closed':
            continue
        tier = str(trade.get('tier') or 'A').upper()
        stats.setdefault(tier, _init_tier_bucket())
        size = _safe_float(trade.get('position_size_usd'))
        pnl = _safe_float(trade.get('pnl_percent'))
        stats[tier]['closed'] += 1
        stats[tier]['realized'] += size * pnl / 100.0
    return stats


def _tier_a_regime_from_movers(movers: List[Dict]) -> bool:
    if not movers:
        return False
    strong = 0
    total = 0.0
    for mover in movers:
        score = _safe_float(mover.get('score'))
        momentum = _safe_float(mover.get('momentum'))
        volume = _safe_float(mover.get('volume'))
        total += score
        if momentum >= 5.0 and score >= 0.45 and volume >= 5_000_000:
            strong += 1
    avg_score = total / len(movers) if movers else 0.0
    return strong >= 1 and avg_score >= 0.45


def _format_tier_breakdown(stats: Dict[str, Dict], guard: Dict) -> str:
    lines = []
    for tier in ('A', 'B'):
        bucket = stats.get(tier, _init_tier_bucket())
        lines.append(
            f"- Tier {tier}: open {bucket['open']}, closed {bucket['closed']}, "
            f"unrlzd {_format_usd(bucket['unrealized'], show_sign=True)}, rlzd {_format_usd(bucket['realized'], show_sign=True)}"
        )
    guard_status = "PAUSED" if guard.get('paused') else 'Active'
    guard_pnl = _format_usd(_safe_float(guard.get('realized_pnl')), show_sign=True)
    guard_session = guard.get('session_start') or 'n/a'
    lines.append(f"- Tier B guard: {guard_status}, PnL {guard_pnl} since {guard_session}")
    return "\n".join(lines)


def _load_alerts() -> List[Dict]:
    if not ALERT_LOG_PATH.exists():
        return []
    alerts: List[Dict] = []
    with ALERT_LOG_PATH.open('r', encoding='utf-8') as handle:
        for raw in handle:
            line = raw.strip()
            if not line:
                continue
            try:
                alerts.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return alerts


def _fetch_binance(endpoint: str, params: Dict) -> Optional[Dict]:
    query = parse.urlencode(params)
    url = f"{endpoint}?{query}"
    req = request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with request.urlopen(req, timeout=5) as resp:
            log_api_call('binance')
            return json.load(resp)
    except Exception:
        return None


def _summarize_binance(symbol: str) -> Optional[Dict]:
    pair = f"{symbol.upper()}USDT"
    depth = _fetch_binance(BINANCE_DEPTH_URL, {'symbol': pair, 'limit': 20})
    if not depth:
        return None
    bids = depth.get('bids', [])[:5]
    asks = depth.get('asks', [])[:5]
    bid_liq = sum(float(price) * float(qty) for price, qty in bids)
    ask_liq = sum(float(price) * float(qty) for price, qty in asks)
    trades = _fetch_binance(BINANCE_TRADES_URL, {'symbol': pair, 'limit': 40}) or []
    buy_vol = sum(float(t.get('qty', 0)) for t in trades if not t.get('isBuyerMaker'))
    sell_vol = sum(float(t.get('qty', 0)) for t in trades if t.get('isBuyerMaker'))
    total_vol = buy_vol + sell_vol if (buy_vol + sell_vol) else 1.0
    buy_pressure = buy_vol / total_vol
    return {
        'pair': pair,
        'bid_liquidity': bid_liq,
        'ask_liquidity': ask_liq,
        'buy_pressure': buy_pressure
    }


def _format_alerts(alerts: List[Dict]) -> str:
    if not alerts:
        return "No new alerts."
    lines = []
    for alert in alerts[:5]:
        token = alert.get('token', '?')
        reason = alert.get('reason', 'alert')
        pnl = _safe_float(alert.get('pnl_percent'))
        when = _format_dt(alert.get('timestamp'))
        lines.append(f"- {token} {pnl:+.2f}% — {reason} @ {when}")
    remaining = len(alerts) - 5
    if remaining > 0:
        lines.append(f"… +{remaining} more")
    return "\n".join(lines)


def _calculate_unrealized(open_positions: List[Dict]) -> float:
    total = 0.0
    for pos in open_positions:
        size = _safe_float(pos.get('position_size_usd'))
        pnl = _safe_float(pos.get('pnl_percent'))
        total += size * pnl / 100.0
    return total


def _compute_trade_metrics(trades: List[Dict]) -> Dict:
    closed = [trade for trade in trades if str(trade.get('status', '')).lower() == 'closed']
    closed_sorted = sorted(
        closed,
        key=lambda trade: _parse_dt(trade.get('exit_time') or trade.get('last_updated') or '') or datetime.min,
        reverse=True
    )
    wins = [trade for trade in closed if _safe_float(trade.get('pnl_percent')) > 0]
    win_rate = (len(wins) / len(closed) * 100.0) if closed else 0.0

    pnl_usd = [
        _safe_float(trade.get('position_size_usd')) * _safe_float(trade.get('pnl_percent')) / 100.0
        for trade in closed
    ]
    hold_hours = []
    for trade in closed:
        entry_dt = _parse_dt(trade.get('entry_time'))
        exit_dt = _parse_dt(trade.get('exit_time'))
        if entry_dt and exit_dt:
            hours = (exit_dt - entry_dt).total_seconds() / 3600.0
            hold_hours.append(hours if hours > 0 else 0.0)

    return {
        'closed_trades': closed,
        'recent_closed': closed_sorted,
        'win_rate': win_rate,
        'total_closed': len(closed),
        'realized_pnl_usd': sum(pnl_usd),
        'average_hold_hours': mean(hold_hours) if hold_hours else 0.0,
    }


def _load_state() -> Dict:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return {}


def _load_last_success_timestamp():
    state = _load_state()
    ts = state.get('last_success_ts')
    if not ts:
        return None
    return _parse_dt(ts)


def _save_state(state: Dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding='utf-8')


def _build_snapshot_line(current: Dict, previous: Dict, loop_health: str) -> str:
    open_count = current['open_positions']
    realized = current['realized_pnl_usd']
    unrealized = current['unrealized_pnl_usd']
    win_rate = current['win_rate']

    prev_open = previous.get('open_positions') if previous else None
    prev_realized = previous.get('realized_pnl_usd') if previous else None
    prev_unrealized = previous.get('unrealized_pnl_usd') if previous else None
    prev_win = previous.get('win_rate') if previous else None

    parts = [
        f"Open: {open_count} ({_format_delta(open_count, prev_open, 'count')})",
        f"Realized: {_format_usd(realized)} ({_format_delta(realized, prev_realized, 'usd')})",
        f"Unrealized: {_format_usd(unrealized)} ({_format_delta(unrealized, prev_unrealized, 'usd')})",
        f"Win rate: {win_rate:.1f}% ({_format_delta(win_rate, prev_win, 'percent')})",
        f"Loop: {loop_health}"
    ]
    return " | ".join(parts)



def _build_cycle_message(cycle_number: int, prev_state: Dict) -> Dict:
    open_positions = _load_json_list(OPEN_POSITIONS_PATH)
    trades = _load_json_list(TRADES_LOG_PATH)
    baseline_str, baseline_dt = _load_run_baseline()

    run_open_positions: List[Dict] = []
    carryover_open_positions: List[Dict] = []
    for pos in open_positions:
        entry_dt = _parse_dt(pos.get('entry_time') or pos.get('signal_timestamp') or pos.get('last_update'))
        if baseline_dt and entry_dt and entry_dt < baseline_dt:
            carryover_open_positions.append(pos)
        else:
            run_open_positions.append(pos)

    def _within_run(trade: Dict) -> bool:
        exit_dt = _parse_dt(trade.get('exit_time') or trade.get('last_update'))
        if not baseline_dt or not exit_dt:
            return True
        return exit_dt >= baseline_dt

    run_trades = [trade for trade in trades if _within_run(trade)]

    metrics = _compute_trade_metrics(run_trades)
    realized_pnl = metrics['realized_pnl_usd']
    unrealized_pnl = _calculate_unrealized(run_open_positions)
    loop_health = _load_loop_health()
    top_movers = _load_top_movers()
    alerts = _load_alerts()
    tier_guard = _load_tier_b_guard()
    tier_stats = _summarize_by_tier(run_open_positions, run_trades)
    market_snapshot = _load_market_state_snapshot()
    session_guard = _load_session_guard_snapshot()

    current_metrics = {
        'open_positions': len(run_open_positions),
        'closed_total': metrics['total_closed'],
        'win_rate': metrics['win_rate'],
        'realized_pnl_usd': realized_pnl,
        'unrealized_pnl_usd': unrealized_pnl,
    }

    prev_metrics = prev_state.get('metrics', {})
    summary_line = _build_snapshot_line(current_metrics, prev_metrics, loop_health)

    prev_trade_count = prev_state.get('trade_count', 0)
    if prev_trade_count < 0 or prev_trade_count > len(run_trades):
        prev_trade_count = len(run_trades)
    new_trades = run_trades[prev_trade_count:] if prev_trade_count <= len(run_trades) else []
    trade_exit_text = _format_trade_exits(new_trades)

    prev_tokens = prev_state.get('open_tokens', [])
    current_tokens = [pos.get('token', '?') for pos in run_open_positions]
    entries = sorted(set(current_tokens) - set(prev_tokens))
    exits = sorted(set(prev_tokens) - set(current_tokens))
    position_delta_text = _format_position_deltas(entries, exits)

    tier_a_gate = any((m.get('score') or 0) >= 0.45 and (m.get('momentum') or 0) >= 5 for m in top_movers[:TOP_MOVER_LIMIT])
    enriched_movers = []
    for mover in top_movers[:TOP_MOVER_LIMIT]:
        enriched_movers.append((mover, _summarize_binance(mover['token'])))

    guard_net = tier_guard.get('net_pnl')
    if guard_net is None:
        guard_net = _safe_float(tier_guard.get('realized_pnl')) + _safe_float(tier_guard.get('unrealized_pnl'))

    mode_line = _format_mode_line(market_snapshot)
    guard_line = _format_guard_line(session_guard)

    insights = []
    if not tier_a_gate:
        insights.append("Tier A gate CLOSED")
    if tier_guard.get('paused'):
        insights.append(f"Tier B paused ({_format_usd(guard_net, show_sign=True)})")
    else:
        insights.append(f"Tier B net {_format_usd(guard_net, show_sign=True)}")
    if not insights:
        insights.append("Systems nominal")
    insight_line = " | ".join(insights)

    timestamp_text = datetime.now(LOCAL_TZ or timezone.utc).strftime('%Y-%m-%d %H:%M %Z')

    signal_lines = []
    if enriched_movers:
        for mover, liquidity in enriched_movers:
            token = mover.get('token', '?')
            momentum = _safe_float(mover.get('momentum'))
            volume = _safe_float(mover.get('volume'))
            trend = mover.get('trend') or mover.get('status') or 'n/a'
            if liquidity:
                bid_liq = _format_usd(liquidity['bid_liquidity'])
                ask_liq = _format_usd(liquidity['ask_liquidity'])
                buy_pct = int(liquidity['buy_pressure'] * 100)
                signal_lines.append(
                    f"- {token} {momentum:+.1f}% | vol {_format_usd(volume)} | {trend} | Binance bid {bid_liq} / ask {ask_liq} | buy {buy_pct}%"
                )
            else:
                signal_lines.append(
                    f"- {token} {momentum:+.1f}% | vol {_format_usd(volume)} | {trend} (no Binance pair)"
                )
    else:
        signal_lines.append("No fresh scanner signals.")

    prev_alert_count = prev_state.get('alert_count', 0)
    if prev_alert_count < 0 or prev_alert_count > len(alerts):
        prev_alert_count = len(alerts)
    new_alerts = alerts[prev_alert_count:]
    alerts_text = _format_alerts(list(reversed(new_alerts))) if new_alerts else "No new alerts."

    lines = [
        "SYSTEM INSIGHT:",
        insight_line,
        mode_line,
        guard_line,
    ]
    if baseline_str:
        lines.append(f"Run baseline: {baseline_str}")
    lines.extend([
        "",
        f"📊 Market state — {timestamp_text}",
        summary_line,
        "",
        "🔥 Signals:",
        *signal_lines,
        "",
        "📈 Positions (this run):",
        _format_active_positions(run_open_positions),
    ])
    if carryover_open_positions:
        lines.extend([
            "",
            "Carryover positions:",
            _format_active_positions(carryover_open_positions),
        ])
    lines.extend([
        "",
        "Changes:",
        position_delta_text or "No run-position changes.",
        "",
        "⚠️ Risk:",
        _format_tier_breakdown(tier_stats, tier_guard),
        "",
        "Alerts:",
        alerts_text,
        "",
        "Recent exits:",
        trade_exit_text,
    ])

    message = "\n".join(lines).strip()

    new_state = {
        'cycle_count': cycle_number,
        'metrics': current_metrics,
        'trade_count': len(run_trades),
        'open_tokens': current_tokens,
        'top_movers': [m['token'] for m in top_movers],
        'alert_count': len(alerts)
    }

    return {
        'message': message,
        'state_update': new_state
    }


def send_telegram_message(text: str, lane: str = 'trading') -> Dict:
    token = _get_env_var('TELEGRAM_BOT_TOKEN')
    lane_chat_id, lane_thread_id = resolve_lane_target(lane)
    chat_id = lane_chat_id or _get_env_var('TELEGRAM_CHAT_ID')
    payload = {
        'chat_id': chat_id,
        'text': text
    }
    if lane_thread_id:
        payload['message_thread_id'] = lane_thread_id
    data = parse.urlencode(payload).encode('utf-8')
    url = API_URL_TEMPLATE.format(token=token)
    req = request.Request(url, data=data)

    try:
        with request.urlopen(req) as resp:
            content = resp.read().decode('utf-8')
            result = json.loads(content)
    except error.HTTPError as http_err:
        detail = http_err.read().decode('utf-8', errors='ignore')
        raise RuntimeError(f"Telegram API error {http_err.code}: {detail}") from http_err
    except error.URLError as net_err:
        raise RuntimeError(f"Telegram request failed: {net_err.reason}") from net_err

    if not result.get('ok'):
        raise RuntimeError(f"Telegram API responded with failure: {result}")
    return result


def telegram_sender() -> Dict:
    prev_state = _load_state()
    cycle_counter = prev_state.get('cycle_count', 0) + 1
    payload = _build_cycle_message(cycle_counter, prev_state)
    response = send_telegram_message(payload['message'])

    success_ts = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    new_state = {
        'cycle_count': cycle_counter,
        **payload['state_update'],
        'last_success_ts': success_ts
    }
    _save_state(new_state)

    return {
        'cycle_count': cycle_counter,
        'message_preview': payload['message'].split('\n')[0],
        'telegram_response': response
    }


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        outbound = ' '.join(sys.argv[1:])
        api_response = send_telegram_message(outbound)
        print(json.dumps(api_response, indent=2))
    else:
        result = telegram_sender()
        print(json.dumps(result, indent=2))
