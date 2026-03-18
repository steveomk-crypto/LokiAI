import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

WORKSPACE = Path('/data/.openclaw/workspace')
TRADES_LOG = WORKSPACE / 'paper_trades' / 'trades_log.json'
REPORT_DIR = WORKSPACE / 'performance_reports'


def _load_trades():
    if not TRADES_LOG.exists():
        return []
    try:
        return json.loads(TRADES_LOG.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return []


def _parse_hours(entry_time: str, exit_time: str) -> float:
    if not (entry_time and exit_time):
        return 0.0
    try:
        start = datetime.fromisoformat(entry_time.replace('Z', '+00:00'))
        end = datetime.fromisoformat(exit_time.replace('Z', '+00:00'))
    except ValueError:
        return 0.0
    delta = end - start
    return round(abs(delta.total_seconds()) / 3600.0, 2)


def _compute_stats(trades):
    if not trades:
        return {'total_trades': 0, 'win_rate': 0.0, 'avg_pnl': 0.0, 'median_hold_hours': 0.0}
    pnls = [float(t.get('pnl_percent') or 0.0) for t in trades]
    wins = sum(1 for p in pnls if p > 0)
    holds = [float(t.get('hold_hours') or 0.0) for t in trades if t.get('hold_hours') is not None]
    return {
        'total_trades': len(trades),
        'win_rate': round((wins / len(trades)) * 100, 2),
        'avg_pnl': round(mean(pnls), 4),
        'median_hold_hours': round(median(holds), 2) if holds else 0.0,
    }


def _bucket(trades, key):
    buckets = defaultdict(list)
    for trade in trades:
        buckets[str(trade.get(key, 'unknown'))].append(trade)
    return {bucket: _compute_stats(values) for bucket, values in buckets.items()}


def _score_bucket(value):
    if value is None:
        return 'unknown'
    try:
        return f"{round(float(value) / 0.1) * 0.1:.1f}"
    except (TypeError, ValueError):
        return 'unknown'


def _liquidity_bucket(value):
    if value is None:
        return 'unknown'
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 'unknown'
    if value >= 0.7:
        return '0.7+'
    if value >= 0.6:
        return '0.6-0.69'
    if value >= 0.55:
        return '0.55-0.59'
    return '<0.55'


def _bucket_custom(trades, key_func):
    buckets = defaultdict(list)
    for trade in trades:
        buckets[key_func(trade)].append(trade)
    return {bucket: _compute_stats(values) for bucket, values in buckets.items()}


def generate_report():
    trades = [t for t in _load_trades() if str(t.get('status')).lower() == 'closed']
    for trade in trades:
        trade['hold_hours'] = _parse_hours(trade.get('entry_time'), trade.get('exit_time'))
    overall = _compute_stats(trades)
    by_persistence = _bucket(trades, 'persistence')
    by_exit_reason = _bucket(trades, 'exit_reason')
    by_score = _bucket_custom(trades, lambda t: _score_bucket(t.get('score') or t.get('signal_score')))
    by_liquidity = _bucket_custom(trades, lambda t: _liquidity_bucket(t.get('liquidity_score')))

    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H%M%SZ')
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / f'attribute_breakdown_{timestamp}.md'

    lines = [
        f"# Trade Attribute Breakdown ({timestamp})",
        '',
        '## Overall',
        f"- Total trades: {overall['total_trades']}",
        f"- Win rate: {overall['win_rate']:.2f}%",
        f"- Avg PnL: {overall['avg_pnl']:.4f}%",
        f"- Median hold: {overall['median_hold_hours']:.2f} h",
        '',
        '## By Persistence',
    ]
    for bucket, stats in sorted(by_persistence.items(), key=lambda x: float(x[0]) if x[0].isdigit() else 0, reverse=True):
        lines.append(f"- Persistence {bucket}: {stats['total_trades']} trades | Win {stats['win_rate']:.1f}% | Avg PnL {stats['avg_pnl']:.3f}%")
    lines.extend(['', '## By Score Bucket'])
    for bucket, stats in sorted(by_score.items(), key=lambda x: x[0]):
        lines.append(f"- Score {bucket}: {stats['total_trades']} trades | Win {stats['win_rate']:.1f}% | Avg PnL {stats['avg_pnl']:.3f}%")
    lines.extend(['', '## By Liquidity Score'])
    for bucket, stats in sorted(by_liquidity.items(), key=lambda x: x[0]):
        lines.append(f"- Liquidity {bucket}: {stats['total_trades']} trades | Win {stats['win_rate']:.1f}% | Avg PnL {stats['avg_pnl']:.3f}%")
    lines.extend(['', '## By Exit Reason'])
    for bucket, stats in sorted(by_exit_reason.items(), key=lambda x: stats_sort_key(x[0])):
        lines.append(f"- {bucket}: {stats['total_trades']} trades | Win {stats['win_rate']:.1f}% | Avg PnL {stats['avg_pnl']:.3f}%")
    lines.extend(['', '## By Score Bucket'])
    for bucket, stats in sorted(by_score.items(), key=lambda x: x[0]):
        lines.append(f"- Score {bucket}: {stats['total_trades']} trades | Win {stats['win_rate']:.1f}% | Avg PnL {stats['avg_pnl']:.3f}%")
    lines.extend(['', '## By Liquidity Score'])
    for bucket, stats in sorted(by_liquidity.items(), key=lambda x: x[0]):
        lines.append(f"- Liquidity {bucket}: {stats['total_trades']} trades | Win {stats['win_rate']:.1f}% | Avg PnL {stats['avg_pnl']:.3f}%")

    report_path.write_text("\n".join(lines), encoding='utf-8')
    summary = {
        'timestamp': timestamp,
        'report_path': str(report_path),
        'overall': overall,
        'by_persistence': by_persistence,
        'by_exit_reason': by_exit_reason,
        'by_score': by_score,
        'by_liquidity': by_liquidity,
    }
    return summary


def stats_sort_key(value: str):
    common = ['Take profit target hit', 'Trailing stop exit', 'Loser control', 'Stop loss hit', 'Time stop']
    for idx, label in enumerate(common):
        if value and value.startswith(label):
            return idx
    return len(common)


if __name__ == '__main__':
    output = generate_report()
    print(json.dumps(output, indent=2))
