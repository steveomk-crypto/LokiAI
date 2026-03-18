import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

TRADES_LOG_PATH = Path("/data/.openclaw/workspace/paper_trades/trades_log.json")
JOURNAL_PATH = Path("/data/.openclaw/workspace/trade_journal/journal.json")


def _load_trades() -> List[Dict]:
    if not TRADES_LOG_PATH.exists():
        return []
    try:
        return json.loads(TRADES_LOG_PATH.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return []


def _save_journal(entries: List[Dict]):
    JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    JOURNAL_PATH.write_text(json.dumps(entries, indent=2), encoding='utf-8')


def _duration_hours(entry_time: str, exit_time: str) -> float:
    try:
        start = datetime.fromisoformat(entry_time.replace('Z', '+00:00'))
        end = datetime.fromisoformat(exit_time.replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return 0.0
    delta = end - start
    return delta.total_seconds() / 3600.0


def _max_drawdown(pnl_sequence: List[float]) -> float:
    peak = 0.0
    trough = 0.0
    max_dd = 0.0
    equity = 0.0
    for pnl in pnl_sequence:
        equity += pnl
        if equity > peak:
            peak = equity
            trough = equity
        if equity < trough:
            trough = equity
            drawdown = peak - trough
            if drawdown > max_dd:
                max_dd = drawdown
    return -max_dd


def trade_journal():
    trades = _load_trades()
    if not trades:
        _save_journal([])
        return {
            'win_rate': 0.0,
            'average_gain': 0.0,
            'average_loss': 0.0,
            'max_drawdown': 0.0,
            'best_signal_source': None,
            'total_trades': 0
        }

    journal_entries = []
    pnl_values = []
    gains = []
    losses = []
    source_perf: Dict[str, List[float]] = {}

    for trade in trades:
        exit_price = trade.get('exit_price')
        exit_time = trade.get('exit_time')
        if exit_price is None or exit_time is None:
            continue
        entry_price = trade.get('entry_price')
        pnl = float(trade.get('pnl_percent') or 0.0)
        duration = _duration_hours(trade.get('entry_time'), exit_time)
        source = trade.get('signal_source', 'market_scanner')
        market_condition = trade.get('market_condition', 'unknown')

        journal_entry = {
            'symbol': trade.get('token'),
            'entry_price': entry_price,
            'exit_price': exit_price,
            'position_size': trade.get('position_size_usd'),
            'pnl_percent': pnl,
            'trade_duration_hours': round(duration, 2),
            'signal_source': source,
            'market_condition': market_condition,
            'entry_time': trade.get('entry_time'),
            'exit_time': exit_time
        }
        journal_entries.append(journal_entry)

        pnl_values.append(pnl)
        if pnl > 0:
            gains.append(pnl)
        elif pnl < 0:
            losses.append(pnl)

        source_perf.setdefault(source, []).append(pnl)

    _save_journal(journal_entries)

    total = len(journal_entries)
    wins = sum(1 for pnl in pnl_values if pnl > 0)
    win_rate = (wins / total * 100) if total else 0.0
    average_gain = sum(gains) / len(gains) if gains else 0.0
    average_loss = sum(losses) / len(losses) if losses else 0.0
    max_drawdown = _max_drawdown(pnl_values) if pnl_values else 0.0

    best_signal_source = None
    best_avg = float('-inf')
    for source, values in source_perf.items():
        if not values:
            continue
        avg = sum(values) / len(values)
        if avg > best_avg:
            best_avg = avg
            best_signal_source = source

    summary = {
        'win_rate': round(win_rate, 2),
        'average_gain': round(average_gain, 2),
        'average_loss': round(average_loss, 2),
        'max_drawdown': round(max_drawdown, 2),
        'best_signal_source': best_signal_source,
        'total_trades': total
    }
    return summary


if __name__ == '__main__':
    result = trade_journal()
    print(json.dumps(result, indent=2))
