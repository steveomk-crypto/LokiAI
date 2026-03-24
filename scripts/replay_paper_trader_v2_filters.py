#!/usr/bin/env python3
import json
from pathlib import Path
from collections import defaultdict

WORKSPACE = Path('/home/lokiai/.openclaw/workspace')
TRADES_PATH = WORKSPACE / 'paper_trades' / 'trades_log_v2.json'
DECISIONS_PATH = WORKSPACE / 'paper_trades' / 'paper_trader_v2_decisions.jsonl'

CONFIGS = [
    {
        'name': 'current_loose',
        'tier_a_min_score': 0.42,
        'tier_b_min_score': 0.30,
        'tier_a_min_drift': 0.10,
        'tier_b_min_drift': 0.08,
        'tier_a_min_persistence': 0,
        'tier_b_min_persistence': 2,
        'reject_stalling': False,
        'p4_score_floor': None,
    },
    {
        'name': 'tight_first_pass',
        'tier_a_min_score': 0.58,
        'tier_b_min_score': 0.45,
        'tier_a_min_drift': 0.12,
        'tier_b_min_drift': 0.10,
        'tier_a_min_persistence': 5,
        'tier_b_min_persistence': 4,
        'reject_stalling': True,
        'p4_score_floor': 0.62,
    },
    {
        'name': 'moderate_v21',
        'tier_a_min_score': 0.55,
        'tier_b_min_score': 0.40,
        'tier_a_min_drift': 0.10,
        'tier_b_min_drift': 0.09,
        'tier_a_min_persistence': 4,
        'tier_b_min_persistence': 4,
        'reject_stalling': True,
        'p4_score_floor': 0.58,
    },
    {
        'name': 'balanced_v22',
        'tier_a_min_score': 0.52,
        'tier_b_min_score': 0.38,
        'tier_a_min_drift': 0.10,
        'tier_b_min_drift': 0.08,
        'tier_a_min_persistence': 4,
        'tier_b_min_persistence': 3,
        'reject_stalling': True,
        'p4_score_floor': 0.56,
    },
]


def load_trades():
    trades = json.loads(TRADES_PATH.read_text())
    return trades if isinstance(trades, list) else []


def load_opens():
    rows = []
    for line in DECISIONS_PATH.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        if obj.get('action') == 'open_position':
            rows.append(obj)
    return rows


def pair_trades(opens, trades):
    used = [False] * len(trades)
    pairs = []
    for op in opens:
        match = None
        for i, trade in enumerate(trades):
            if used[i]:
                continue
            if trade.get('token') == op.get('token') and trade.get('tier') == op.get('tier'):
                match = (i, trade)
                break
        if match is None:
            continue
        i, trade = match
        used[i] = True
        pairs.append((op, trade))
    return pairs


def would_accept(cfg, op, trade):
    score = float(op.get('score') or 0.0)
    drift = float(op.get('drift_300s') or 0.0)
    freshness = float(op.get('freshness_seconds') or 9999.0)
    tier = op.get('tier') or 'B'
    persistence = int(trade.get('persistence') or 0)
    trend = (trade.get('trend') or '').lower()

    if freshness > 180:
        return False, 'stale'
    if drift <= 0:
        return False, 'non_positive_drift'
    if trend in {'isolated spike', 'fading'}:
        return False, 'bad_trend'
    if cfg['reject_stalling'] and trend == 'stalling':
        return False, 'stalling'
    if cfg['p4_score_floor'] is not None and persistence == 4 and score < cfg['p4_score_floor']:
        return False, 'p4_score_floor'

    if tier == 'A':
        ok = (
            score >= cfg['tier_a_min_score']
            and drift >= cfg['tier_a_min_drift']
            and persistence >= cfg['tier_a_min_persistence']
        )
        return ok, 'tier_a_gate' if not ok else 'accept'

    ok = (
        score >= cfg['tier_b_min_score']
        and drift >= cfg['tier_b_min_drift']
        and persistence >= cfg['tier_b_min_persistence']
    )
    return ok, 'tier_b_gate' if not ok else 'accept'


def summarize(cfg, pairs):
    kept = []
    skipped = []
    skip_reasons = defaultdict(int)
    for op, trade in pairs:
        ok, reason = would_accept(cfg, op, trade)
        row = {
            'token': trade.get('token'),
            'tier': trade.get('tier'),
            'pnl_percent': float(trade.get('pnl_percent') or 0.0),
            'exit_reason': trade.get('exit_reason'),
            'score': float(op.get('score') or 0.0),
            'drift_300s': float(op.get('drift_300s') or 0.0),
            'persistence': int(trade.get('persistence') or 0),
            'trend': trade.get('trend'),
        }
        if ok:
            kept.append(row)
        else:
            skipped.append(row)
            skip_reasons[reason] += 1

    def avg(xs):
        return round(sum(xs) / len(xs), 4) if xs else 0.0

    kept_pnls = [r['pnl_percent'] for r in kept]
    skipped_pnls = [r['pnl_percent'] for r in skipped]
    return {
        'config': cfg['name'],
        'matched_trades': len(pairs),
        'kept_count': len(kept),
        'skipped_count': len(skipped),
        'kept_total_pnl': round(sum(kept_pnls), 4),
        'kept_avg_pnl': avg(kept_pnls),
        'kept_win_rate': round((sum(1 for x in kept_pnls if x > 0) / len(kept_pnls)) * 100, 2) if kept_pnls else 0.0,
        'skipped_total_pnl': round(sum(skipped_pnls), 4),
        'skipped_avg_pnl': avg(skipped_pnls),
        'skip_reasons': dict(sorted(skip_reasons.items(), key=lambda kv: (-kv[1], kv[0]))),
        'kept_examples': sorted(kept, key=lambda x: x['pnl_percent'])[:5] + sorted(kept, key=lambda x: x['pnl_percent'], reverse=True)[:5],
    }


def main():
    trades = load_trades()
    opens = load_opens()
    pairs = pair_trades(opens, trades)
    report = [summarize(cfg, pairs) for cfg in CONFIGS]
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
