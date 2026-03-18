import json
import os
from datetime import datetime
from statistics import mean
from typing import Dict, List

TRADES_LOG = "/data/.openclaw/workspace/paper_trades/trades_log.json"
OPEN_POSITIONS = "/data/.openclaw/workspace/paper_trades/open_positions.json"
REPORT_DIR = "/data/.openclaw/workspace/performance_reports"
SUMMARY_LATEST = os.path.join(REPORT_DIR, "summary_latest.txt")
JOURNAL_PATH = "/data/.openclaw/workspace/trade_journal/journal.json"
JOURNAL_REPORT_PATH = "/data/.openclaw/workspace/trade_journal/performance_report.json"


def _load_json(path: str, default):
    if os.path.exists(path):
        with open(path, 'r') as handle:
            try:
                return json.load(handle)
            except json.JSONDecodeError:
                return default
    return default


def _format_pct(value: float) -> str:
    return f"{value:+.2f}%"


def _avg(values: List[float]) -> float:
    return mean(values) if values else 0.0


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


def _token_averages(trades: List[Dict]):
    buckets: Dict[str, List[float]] = {}
    for trade in trades:
        token = trade.get('token')
        pnl = trade.get('pnl_percent')
        if token and pnl is not None:
            buckets.setdefault(token, []).append(float(pnl))
    averages = [(token, _avg(pnls)) for token, pnls in buckets.items()]
    best = [item for item in sorted(averages, key=lambda x: x[1], reverse=True) if item[1] > 0][:3]
    worst = [item for item in sorted(averages, key=lambda x: x[1]) if item[1] < 0][:3]
    return best, worst


def _strategy_note(total_pnl: float, tp_hits: int, sl_hits: int) -> str:
    if total_pnl >= 0 and tp_hits >= sl_hits:
        verdict = "acceptable"
    elif sl_hits > tp_hits:
        verdict = "too strict"
    else:
        verdict = "too loose"
    detail = (
        f"Thresholds appear {verdict} based on {tp_hits} TP vs {sl_hits} SL hits and total PnL {total_pnl:+.2f}%."
    )
    return detail


def _bucket_duration(hours: float) -> str:
    if hours < 1:
        return "under_1h"
    if hours < 6:
        return "1h_to_6h"
    return "over_6h"


def _aggregate_perf(entries: List[Dict], key: str):
    buckets: Dict[str, List[float]] = {}
    for entry in entries:
        bucket_key = entry.get(key)
        pnl = entry.get('pnl_percent')
        if bucket_key is None or pnl is None:
            continue
        buckets.setdefault(bucket_key, []).append(float(pnl))
    return buckets


def _ranking_list(buckets: Dict[str, List[float]], top: bool = True, limit: int = 3):
    items = []
    for bucket_key, values in buckets.items():
        if not values:
            continue
        avg = sum(values) / len(values)
        items.append((bucket_key, avg))
    items.sort(key=lambda x: x[1], reverse=top)
    return items[:limit]


def journal_performance():
    entries: List[Dict] = _load_json(JOURNAL_PATH, [])
    if not entries:
        _save_report = {
            'win_rate': 0.0,
            'average_gain': 0.0,
            'average_loss': 0.0,
            'max_drawdown': 0.0,
            'best_signal_sources': [],
            'worst_signal_sources': [],
            'profitable_symbols': [],
            'losing_symbols': [],
            'winning_signals': [],
            'losing_signals': [],
            'duration_trends': []
        }
        os.makedirs(os.path.dirname(JOURNAL_REPORT_PATH), exist_ok=True)
        with open(JOURNAL_REPORT_PATH, 'w') as handle:
            json.dump(_save_report, handle, indent=2)
        return _save_report

    pnl_values = [float(e.get('pnl_percent') or 0.0) for e in entries]
    wins = [p for p in pnl_values if p > 0]
    losses = [p for p in pnl_values if p < 0]
    win_rate = (len(wins) / len(pnl_values) * 100) if pnl_values else 0.0
    average_gain = sum(wins) / len(wins) if wins else 0.0
    average_loss = sum(losses) / len(losses) if losses else 0.0

    best_symbols = _ranking_list(_aggregate_perf(entries, 'symbol'), top=True, limit=5)
    worst_symbols = _ranking_list(_aggregate_perf(entries, 'symbol'), top=False, limit=5)
    best_sources = _ranking_list(_aggregate_perf(entries, 'signal_source'), top=True, limit=3)
    worst_sources = _ranking_list(_aggregate_perf(entries, 'signal_source'), top=False, limit=3)

    signal_stats = {}
    for entry in entries:
        source = entry.get('signal_source', 'unknown')
        pnl = float(entry.get('pnl_percent') or 0.0)
        stats = signal_stats.setdefault(source, {'wins': 0, 'total': 0, 'pnl': []})
        if pnl > 0:
            stats['wins'] += 1
        stats['total'] += 1
        stats['pnl'].append(pnl)

    winning_signals = []
    losing_signals = []
    for source, stats in signal_stats.items():
        if not stats['total']:
            continue
        win_rate_source = stats['wins'] / stats['total'] * 100
        avg_pnl = sum(stats['pnl']) / stats['total']
        if win_rate_source >= 70 and avg_pnl > 0:
            winning_signals.append({'signal_source': source, 'win_rate': round(win_rate_source, 2), 'avg_pnl': round(avg_pnl, 2)})
        if win_rate_source <= 30 and avg_pnl < 0:
            losing_signals.append({'signal_source': source, 'win_rate': round(win_rate_source, 2), 'avg_pnl': round(avg_pnl, 2)})

    duration_buckets: Dict[str, List[float]] = {}
    for entry in entries:
        duration = float(entry.get('trade_duration_hours') or 0.0)
        bucket = _bucket_duration(duration)
        duration_buckets.setdefault(bucket, []).append(float(entry.get('pnl_percent') or 0.0))
    duration_trends = [
        {
            'bucket': bucket,
            'average_pnl': round(sum(values) / len(values), 2)
        }
        for bucket, values in duration_buckets.items() if values
    ]
    duration_trends.sort(key=lambda x: x['average_pnl'], reverse=True)

    report = {
        'win_rate': round(win_rate, 2),
        'average_gain': round(average_gain, 2),
        'average_loss': round(average_loss, 2),
        'max_drawdown': round(_max_drawdown(pnl_values), 2) if pnl_values else 0.0,
        'best_signal_sources': best_sources,
        'worst_signal_sources': worst_sources,
        'profitable_symbols': best_symbols,
        'losing_symbols': worst_symbols,
        'winning_signals': winning_signals,
        'losing_signals': losing_signals,
        'duration_trends': duration_trends
    }

    os.makedirs(os.path.dirname(JOURNAL_REPORT_PATH), exist_ok=True)
    with open(JOURNAL_REPORT_PATH, 'w') as handle:
        json.dump(report, handle, indent=2)

    ranking = {
        'best_signal_sources': best_sources,
        'worst_signal_sources': worst_sources,
        'profitable_symbols': best_symbols,
        'losing_symbols': worst_symbols
    }
    report['ranking'] = ranking
    report['report_path'] = JOURNAL_REPORT_PATH
    return report


def performance_analyzer():
    trades: List[Dict] = _load_json(TRADES_LOG, [])
    open_positions: List[Dict] = _load_json(OPEN_POSITIONS, [])

    total_trades = len(trades)
    pnl_values = [float(t.get('pnl_percent', 0.0)) for t in trades]
    wins = [p for p in pnl_values if p > 0]
    losses = [p for p in pnl_values if p < 0]
    tp_hits = sum(1 for t in trades if t.get('exit_reason') == 'take_profit')
    sl_hits = sum(1 for t in trades if t.get('exit_reason') == 'stop_loss')

    metrics = {
        'total_trades': total_trades,
        'win_rate_pct': (len(wins) / total_trades * 100) if total_trades else 0.0,
        'avg_win_pct': _avg(wins),
        'avg_loss_pct': _avg(losses),
        'total_pnl_pct': sum(pnl_values),
        'tp_hits': tp_hits,
        'sl_hits': sl_hits
    }

    best_tokens, worst_tokens = _token_averages(trades)

    open_summary = [
        f"{pos.get('token', '?')} {_format_pct(float(pos.get('pnl_percent', 0.0)))}"
        for pos in open_positions
    ]

    closed_summary = [
        f"{trade.get('token', '?')} {_format_pct(float(trade.get('pnl_percent', 0.0)))}"
        for trade in trades
    ]

    note = _strategy_note(metrics['total_pnl_pct'], metrics['tp_hits'], metrics['sl_hits'])

    now = datetime.now()
    timestamp_str = now.strftime("%Y-%m-%d %H:%M")
    file_suffix = now.strftime("%Y_%m_%d_%H%M")
    report_path = os.path.join(REPORT_DIR, f"report_{file_suffix}.txt")
    os.makedirs(REPORT_DIR, exist_ok=True)

    def _fmt_token_list(items: List[tuple]) -> str:
        if not items:
            return "None"
        return "\n".join(f"- {token}: {_format_pct(avg)}" for token, avg in items)

    report_lines = [
        f"Paper Trader Performance Report — {timestamp_str}",
        "",
        "Metrics:",
        f"- Total trades: {metrics['total_trades']}",
        f"- Win rate: {metrics['win_rate_pct']:.2f}%",
        f"- Average win: {_format_pct(metrics['avg_win_pct'])}",
        f"- Average loss: {_format_pct(metrics['avg_loss_pct'])}",
        f"- Total PnL: {_format_pct(metrics['total_pnl_pct'])}",
        f"- TP hits: {metrics['tp_hits']}",
        f"- SL hits: {metrics['sl_hits']}",
        "",
        "Best performing tokens:",
        _fmt_token_list(best_tokens),
        "",
        "Worst performing tokens:",
        _fmt_token_list(worst_tokens),
        "",
        "Currently open positions:",
        "\n".join(open_summary) if open_summary else "None",
        "",
        "Strategy Notes:",
        note
    ]

    report_text = "\n".join(report_lines).strip() + "\n"

    with open(report_path, 'w') as handle:
        handle.write(report_text)
    with open(SUMMARY_LATEST, 'w') as handle:
        handle.write(report_text)

    return {
        'metrics': metrics,
        'best_tokens': best_tokens,
        'worst_tokens': worst_tokens,
        'open_positions': open_positions,
        'report_path': report_path,
        'summary_path': SUMMARY_LATEST,
        'report_text': report_text
    }


if __name__ == "__main__":
    result = performance_analyzer()
    print(json.dumps(result, indent=2))
