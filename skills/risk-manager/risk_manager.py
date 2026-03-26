import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from strategy_config import get_strategy_value

OPEN_POSITIONS_PATH = Path("/home/lokiai/.openclaw/workspace/paper_trades/open_positions.json")
TRADES_LOG_PATH = Path("/home/lokiai/.openclaw/workspace/paper_trades/trades_log.json")
RISK_LOG_PATH = Path("/home/lokiai/.openclaw/workspace/risk_logs/risk_decisions.json")

MAX_OPEN_POSITIONS = 15
MAX_RISK_PERCENT = 1.0  # 1% per trade baseline
MAX_CONSECUTIVE_LOSSES = 3
DAILY_DRAWDOWN_LIMIT = -5.0  # percent
MIN_CONFIDENCE = 0.3
MIN_LIQUIDITY_SCORE = 0.45
MIN_LIQUIDITY_CHANGE_RATIO = 1.0
MIN_VOLUME_USD = 100000.0
DEFAULT_ACCOUNT_SIZE = 10000.0
DEFAULT_POSITION_RISK_USD = 100.0


def _load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            return default
    return default


def _consecutive_losses(trades: List[Dict], limit: int, tier_filter: str = 'A') -> int:
    count = 0
    for trade in reversed(trades):
        if tier_filter == 'A' and (trade.get('tier') or 'A') == 'B':
            continue
        pnl = trade.get('pnl_percent')
        if pnl is None:
            continue
        reason = (trade.get('exit_reason') or '').lower()
        if 'manual_trim' in reason or 'manual flatten' in reason:
            continue
        if pnl < 0:
            count += 1
            if count >= limit:
                return count
        else:
            break
    return count


def _daily_drawdown(trades: List[Dict], tier_filter: str = 'A') -> float:
    if not trades:
        return 0.0
    today = datetime.now(timezone.utc).date()
    drawdown = 0.0
    for trade in trades:
        if tier_filter == 'A' and (trade.get('tier') or 'A') == 'B':
            continue
        exit_time = trade.get('exit_time')
        pnl = trade.get('pnl_percent')
        if not exit_time or pnl is None:
            continue
        try:
            exit_date = datetime.fromisoformat(exit_time.replace('Z', '+00:00')).date()
        except ValueError:
            continue
        if exit_date == today:
            drawdown += float(pnl)
    return drawdown


def _ensure_log_dir():
    RISK_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


def _append_risk_log(entry: Dict):
    _ensure_log_dir()
    records = _load_json(RISK_LOG_PATH, [])
    records.append(entry)
    RISK_LOG_PATH.write_text(json.dumps(records, indent=2), encoding='utf-8')


def risk_manager(signal: Optional[Dict] = None, account_size: float = DEFAULT_ACCOUNT_SIZE):
    open_positions = _load_json(OPEN_POSITIONS_PATH, [])
    closed_trades = _load_json(TRADES_LOG_PATH, [])
    tier_a_positions = [pos for pos in open_positions if (pos.get('tier') or 'A') != 'B']

    reasons = []
    decision = "APPROVED"

    if len(tier_a_positions) >= MAX_OPEN_POSITIONS:
        reasons.append(f"Max open positions reached ({len(tier_a_positions)}/{MAX_OPEN_POSITIONS})")

    losses = _consecutive_losses(closed_trades, MAX_CONSECUTIVE_LOSSES, tier_filter='A')
    if losses >= MAX_CONSECUTIVE_LOSSES:
        reasons.append(f"{losses} consecutive losses")

    drawdown = _daily_drawdown(closed_trades, tier_filter='A')
    if drawdown <= DAILY_DRAWDOWN_LIMIT:
        reasons.append(f"Daily drawdown {drawdown:.2f}% exceeds limit {DAILY_DRAWDOWN_LIMIT}%")

    signal = signal or {}
    configured_min = int(get_strategy_value("persistence_requirement") or 1)
    adaptive_persistence = configured_min
    if losses >= 2 or drawdown <= -2.0:
        adaptive_persistence = max(configured_min, 5)
    momentum_floor = float(get_strategy_value("momentum_threshold") or 0.0)
    persistence = signal.get('persistence', adaptive_persistence)
    confidence = signal.get('score', 1.0)
    proposed_risk = signal.get('risk_usd', DEFAULT_POSITION_RISK_USD)
    liquidity_score = signal.get('liquidity_score')
    base_risk_usd = account_size * (MAX_RISK_PERCENT / 100)
    bonus_risk = 0.0
    if persistence >= 5 and liquidity_score is not None and liquidity_score >= 0.65:
        bonus_risk = base_risk_usd * 0.2
    max_risk_usd = base_risk_usd + bonus_risk
    volume_usd = signal.get('volume')
    momentum_value = signal.get('momentum')
    liquidity_change_ratio = signal.get('liquidity_change_ratio')

    if persistence < adaptive_persistence:
        reasons.append(f"Signal persistence {persistence} below minimum {adaptive_persistence}")
    if confidence < MIN_CONFIDENCE:
        reasons.append(f"Signal confidence {confidence:.2f} below {MIN_CONFIDENCE}")
    if momentum_value is not None and momentum_floor and momentum_value < momentum_floor:
        reasons.append(f"Momentum {momentum_value:.2f} below floor {momentum_floor:.2f}")
    if volume_usd is not None and volume_usd < MIN_VOLUME_USD:
        reasons.append(f"Volume ${volume_usd:,.0f} below ${MIN_VOLUME_USD:,.0f} minimum")
    if liquidity_score is not None and liquidity_score < MIN_LIQUIDITY_SCORE:
        reasons.append(f"Liquidity score {liquidity_score:.2f} below {MIN_LIQUIDITY_SCORE}")
    if liquidity_change_ratio is not None and liquidity_change_ratio < MIN_LIQUIDITY_CHANGE_RATIO:
        reasons.append(f"Liquidity change ratio {liquidity_change_ratio:.2f} below {MIN_LIQUIDITY_CHANGE_RATIO}")
    if proposed_risk > max_risk_usd:
        reasons.append(f"Proposed risk ${proposed_risk:.2f} exceeds cap ${max_risk_usd:.2f}")

    if reasons:
        decision = "BLOCKED"

    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    log_entry = {
        'timestamp': timestamp,
        'decision': decision,
        'reasons': reasons or ["All risk checks passed"],
        'open_positions': len(tier_a_positions),
        'open_positions_total': len(open_positions),
        'consecutive_losses': losses,
        'daily_drawdown_pct': drawdown,
        'signal': {
            'token': signal.get('token'),
            'persistence': persistence,
            'score': confidence,
            'risk_usd': proposed_risk,
            'volume': volume_usd,
            'momentum': momentum_value,
            'liquidity_score': liquidity_score,
            'liquidity_change_ratio': liquidity_change_ratio,
            'tier': signal.get('tier')
        }
    }
    _append_risk_log(log_entry)

    return {
        'decision': decision,
        'reasons': log_entry['reasons'],
        'open_positions': len(open_positions),
        'consecutive_losses': losses,
        'daily_drawdown_pct': drawdown
    }


if __name__ == '__main__':
    result = risk_manager()
    lines = [
        f'🛡️ Risk manager: {result["decision"]}',
        f'Open positions: {result["open_positions"]}',
        f'Consecutive losses: {result["consecutive_losses"]}',
        f'Daily PnL today: {result["daily_drawdown_pct"]:+.2f}%'
    ]
    if result['reasons']:
        lines.append('Reasons:')
        lines.extend([f'• {reason}' for reason in result['reasons']])
    print("\n".join(lines))
