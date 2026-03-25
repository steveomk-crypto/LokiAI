#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

WORKSPACE = Path('/home/lokiai/.openclaw/workspace')
TRADES_DIR = WORKSPACE / 'paper_trades'
SYSTEM_LOG = WORKSPACE / 'system_logs' / 'autonomous_market_loop.log'
EVALS_PATH = TRADES_DIR / 'v2_candidate_evaluations.jsonl'
AUDIT_PATH = TRADES_DIR / 'paper_trader_v2_audit_summary.json'
OUT_PATH = TRADES_DIR / 'v2_entry_funnel_report.json'
WINDOW_MINUTES = 90


def parse_ts(value: str | None):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def load_recent_loop_runs(since_dt: datetime):
    runs = []
    if not SYSTEM_LOG.exists():
        return runs
    for raw in SYSTEM_LOG.read_text(encoding='utf-8').splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except Exception:
            continue
        ts = parse_ts(row.get('timestamp'))
        if not ts or ts < since_dt:
            continue
        task = row.get('task')
        if task not in {'market_scanner', 'paper_trader', 'position_manager'}:
            continue
        runs.append(row)
    return runs


def load_recent_evals(since_dt: datetime):
    evals = []
    if not EVALS_PATH.exists():
        return evals
    for raw in EVALS_PATH.read_text(encoding='utf-8').splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except Exception:
            continue
        ts = parse_ts(row.get('timestamp'))
        if not ts or ts < since_dt:
            continue
        evals.append(row)
    return evals


def main() -> int:
    now = datetime.now(timezone.utc)
    since_dt = now - timedelta(minutes=WINDOW_MINUTES)
    loop_rows = load_recent_loop_runs(since_dt)
    eval_rows = load_recent_evals(since_dt)

    scanner_rows = [r for r in loop_rows if r.get('task') == 'market_scanner']
    trader_rows = [r for r in loop_rows if r.get('task') == 'paper_trader']

    scanner_runs = len(scanner_rows)
    scanner_zero = 0
    scanner_nonzero = 0
    surfaced_tokens = Counter()
    for row in scanner_rows:
        details = row.get('details') or {}
        signals = int(details.get('signals') or 0)
        if signals > 0:
            scanner_nonzero += 1
        else:
            scanner_zero += 1
        summary = details.get('summary') or {}
        for opp in summary.get('top_opportunities') or []:
            token = str(opp.get('token') or '').upper()
            if token:
                surfaced_tokens[token] += 1

    trader_watch = 0
    trader_engaged = 0
    shortlist_zero = 0
    shortlist_nonzero = 0
    new_positions = 0
    closed_positions = 0
    for row in trader_rows:
        message = row.get('message') or {}
        if isinstance(message, dict):
            mode = str(message.get('mode') or '').lower()
            if mode == 'watch':
                trader_watch += 1
            elif mode == 'engaged':
                trader_engaged += 1
            if int(message.get('shortlist_count') or 0) > 0:
                shortlist_nonzero += 1
            else:
                shortlist_zero += 1
            new_positions += int(message.get('new_positions_count') or 0)
            closed_positions += int(message.get('closed_positions_count') or 0)

    reject_reasons = Counter()
    accepted_tokens = Counter()
    rejected_tokens = Counter()
    token_reject_reasons = defaultdict(Counter)
    for row in eval_rows:
        token = str(row.get('token') or '').upper()
        if row.get('decision') == 'accept':
            accepted_tokens[token] += 1
        elif row.get('decision') == 'reject':
            reason = str(row.get('reason') or 'unknown')
            reject_reasons[reason] += 1
            rejected_tokens[token] += 1
            token_reject_reasons[token][reason] += 1

    dominant_tokens = []
    for token, count in surfaced_tokens.most_common(10):
        dominant_tokens.append({
            'token': token,
            'scanner_mentions': count,
            'accepted': accepted_tokens.get(token, 0),
            'rejected': rejected_tokens.get(token, 0),
            'top_reject_reasons': dict(token_reject_reasons[token].most_common(3)),
        })

    audit = {}
    if AUDIT_PATH.exists():
        try:
            audit = json.loads(AUDIT_PATH.read_text(encoding='utf-8'))
        except Exception:
            audit = {}

    report = {
        'generated_at': now.isoformat(),
        'window_minutes': WINDOW_MINUTES,
        'scanner': {
            'runs': scanner_runs,
            'nonzero_signal_runs': scanner_nonzero,
            'zero_signal_runs': scanner_zero,
            'top_surfaced_tokens': dict(surfaced_tokens.most_common(10)),
        },
        'trader': {
            'runs': len(trader_rows),
            'watch_runs': trader_watch,
            'engaged_runs': trader_engaged,
            'shortlist_nonzero_runs': shortlist_nonzero,
            'shortlist_zero_runs': shortlist_zero,
            'new_positions_total': new_positions,
            'closed_positions_total': closed_positions,
        },
        'candidate_flow': {
            'eval_count': len(eval_rows),
            'accepted_count': sum(accepted_tokens.values()),
            'rejected_count': sum(reject_reasons.values()),
            'top_reject_reasons': dict(reject_reasons.most_common(10)),
        },
        'dominant_tokens': dominant_tokens,
        'latest_audit': {
            'timestamp': audit.get('timestamp'),
            'mode': audit.get('mode'),
            'active_slot_count': audit.get('active_slot_count'),
            'closed_trade_count': audit.get('closed_trade_count'),
            'win_count': audit.get('win_count'),
            'loss_count': audit.get('loss_count'),
            'avg_win_pct': audit.get('avg_win_pct'),
            'avg_loss_pct': audit.get('avg_loss_pct'),
        },
    }
    OUT_PATH.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
