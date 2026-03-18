#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

TRADES_LOG_PATH = Path('/data/.openclaw/workspace/paper_trades/trades_log.json')


def parse_iso(ts: str):
    if not ts:
        return None
    value = ts
    if value.endswith('Z'):
        value = value[:-1] + '+00:00'
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def main():
    if not TRADES_LOG_PATH.exists():
        print('Session summary: no trades log found')
        return
    try:
        trades = json.loads(TRADES_LOG_PATH.read_text())
    except json.JSONDecodeError:
        print('Session summary: unable to parse trades log')
        return
    today = datetime.now(timezone.utc).date()
    closed = []
    for trade in trades:
        exit_time = trade.get('exit_time') or trade.get('last_update')
        exit_dt = parse_iso(exit_time)
        if not exit_dt or exit_dt.date() != today:
            continue
        closed.append(trade)
    if not closed:
        print(f'Session summary ({today} UTC): no trades closed today.')
        return
    realized_usd = sum(float(t.get('pnl_usd') or 0.0) for t in closed)
    wins = sum(1 for t in closed if float(t.get('pnl_percent') or 0.0) > 0)
    losses = sum(1 for t in closed if float(t.get('pnl_percent') or 0.0) <= 0)
    total = len(closed)
    win_rate = (wins / total) * 100.0 if total else 0.0
    best = max(closed, key=lambda t: float(t.get('pnl_percent') or 0.0))
    worst = min(closed, key=lambda t: float(t.get('pnl_percent') or 0.0))
    print(f'Session summary ({today} UTC)')
    print(f'Trades closed: {total} | Win rate: {win_rate:.1f}% ({wins}-{losses})')
    print(f'Realized PnL: {realized_usd:+.2f} USD')
    print(f"Best: {best.get('token')} {float(best.get('pnl_percent') or 0.0):+.2f}%")
    print(f"Worst: {worst.get('token')} {float(worst.get('pnl_percent') or 0.0):+.2f}%")


if __name__ == '__main__':
    main()
