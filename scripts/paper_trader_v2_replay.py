#!/usr/bin/env python3
import importlib.util
import json
import tempfile
from collections import defaultdict
from copy import deepcopy
from pathlib import Path

WORKSPACE = Path('/home/lokiai/.openclaw/workspace')
SCANNER_LOG = WORKSPACE / 'market_logs' / '2026-03-23.jsonl'
LIVE_TICKERS = WORKSPACE / 'cache' / 'coinbase_tickers.json'
TRADER_PATH = WORKSPACE / 'skills' / 'paper-trader' / 'paper_trader_v2.py'


def load_trader_module():
    spec = importlib.util.spec_from_file_location('paper_trader_v2_replay_module', TRADER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_scanner_runs(path: Path):
    grouped = defaultdict(list)
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line.startswith('{'):
            continue
        row = json.loads(line)
        ts = row.get('timestamp')
        if ts:
            grouped[ts].append(row)
    ordered = []
    for ts in sorted(grouped.keys()):
        rows = sorted(grouped[ts], key=lambda r: r.get('score', 0), reverse=True)
        ordered.append((ts, rows))
    return ordered


def load_live_tickers(path: Path):
    return json.loads(path.read_text())


def build_market_state(ts: str, rows: list[dict]):
    top = rows[:5]
    high_quality = [r for r in rows if (r.get('momentum') or 0) >= 8.0 and (r.get('volume') or 0) >= 75_000_000]
    breadth_positive = sum(1 for r in rows if (r.get('volume_acceleration_ratio') or 0) > 0)
    avg_top_score = sum((r.get('score') or 0) for r in top) / len(top) if top else 0.0
    return {
        'mode': 'replay',
        'computed_at': ts,
        'metrics': {
            'avg_top_score': avg_top_score,
            'high_quality_signals': len(high_quality),
            'breadth_positive': breadth_positive,
            'total_signals': len(rows),
        },
        'top_opportunities': [
            {
                'token': r.get('token'),
                'score': r.get('score'),
                'momentum': r.get('momentum'),
                'volume': r.get('volume'),
                'persistence': r.get('persistence'),
                'status': r.get('status'),
                'trend': r.get('momentum_trend') or r.get('status'),
            }
            for r in top
        ],
    }


def build_tickers(rows: list[dict], live_tickers: dict):
    tickers = {}
    for row in rows:
        symbol = (row.get('token') or '').upper()
        product_id = f'{symbol}-USD'
        live = deepcopy(live_tickers.get(product_id) or {})
        if not live:
            continue
        live['product_id'] = product_id
        live['freshness_seconds'] = 5
        tickers[product_id] = live
    return tickers


def run_replay():
    module = load_trader_module()
    runs = load_scanner_runs(SCANNER_LOG)
    live_tickers = load_live_tickers(LIVE_TICKERS)

    with tempfile.TemporaryDirectory(prefix='paper-v2-replay-') as td:
        td = Path(td)
        module.V2_OPEN_POSITIONS_PATH = td / 'open_positions_v2.json'
        module.V2_TRADES_LOG_PATH = td / 'trades_log_v2.json'
        module.V2_STATE_PATH = td / 'paper_trader_v2_state.json'
        module.V2_DECISIONS_PATH = td / 'paper_trader_v2_decisions.jsonl'
        module.V2_AUDIT_SUMMARY_PATH = td / 'paper_trader_v2_audit_summary.json'

        summary_rows = []
        for ts, rows in runs[-20:]:
            market_state = build_market_state(ts, rows)
            tickers = build_tickers(rows, live_tickers)
            state = module._load_trader_state()
            open_positions = module._normalize_open_positions(module._load_json(module.V2_OPEN_POSITIONS_PATH, []))
            trades_log = module._load_json(module.V2_TRADES_LOG_PATH, [])

            refreshed_positions, closed_positions = module._refresh_positions(open_positions, tickers)
            if closed_positions:
                trades_log.extend(closed_positions)
            shortlist = module._build_shortlist(market_state, tickers, state)
            updated_positions, new_positions = module._open_slots(shortlist, refreshed_positions, state)

            cycle_summary = {
                'timestamp': ts,
                'shortlist_count': len(shortlist),
                'new_positions': [p.get('token') for p in new_positions],
                'open_positions': [p.get('token') for p in updated_positions],
                'closed_positions': [p.get('token') for p in closed_positions],
            }
            summary_rows.append(cycle_summary)

            audit_summary = module._build_audit_summary(updated_positions, trades_log, {
                'timestamp': ts,
                'mode': 'watch' if not updated_positions else 'engaged',
                'active_slot_count': len(updated_positions),
                'shortlist_count': len(shortlist),
                'new_positions_count': len(new_positions),
                'closed_positions_count': len(closed_positions),
                'tier_a_candidates': sum(1 for c in shortlist if c['tier'] == 'A'),
                'tier_b_candidates': sum(1 for c in shortlist if c['tier'] == 'B'),
                'websocket_connected': True,
                'top_candidates': shortlist[:5],
            })

            module._write_json(module.V2_OPEN_POSITIONS_PATH, updated_positions)
            module._write_json(module.V2_TRADES_LOG_PATH, trades_log)
            module._write_json(module.V2_STATE_PATH, state)
            module._write_json(module.V2_AUDIT_SUMMARY_PATH, audit_summary)

        final_open = module._load_json(module.V2_OPEN_POSITIONS_PATH, [])
        final_trades = module._load_json(module.V2_TRADES_LOG_PATH, [])
        final_audit = module._load_json(module.V2_AUDIT_SUMMARY_PATH, {})
        return {
            'cycles_tested': len(summary_rows),
            'cycle_summaries': summary_rows,
            'final_open_positions': final_open,
            'final_closed_count': len(final_trades),
            'final_audit': final_audit,
        }


if __name__ == '__main__':
    print(json.dumps(run_replay(), indent=2))
