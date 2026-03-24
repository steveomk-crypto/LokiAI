#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from importlib.machinery import SourceFileLoader
from pathlib import Path
import sys

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.append(str(WORKSPACE))
SOL_PAPER_TRADER_PATH = WORKSPACE / 'skills' / 'sol-paper-trader' / 'sol_paper_trader.py'
OPEN_POSITIONS_PATH = WORKSPACE / 'sol_paper_trades' / 'open_positions.json'
STATE_PATH = WORKSPACE / 'sol_paper_trades' / 'shadow_fill_state.json'
LOG_PATH = WORKSPACE / 'sol_paper_trades' / 'shadow_fill_log.jsonl'

sol_module = SourceFileLoader('sol_paper_trader_shadow', str(SOL_PAPER_TRADER_PATH)).load_module()


def _load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            return default
    return default


def _append_log(entry: dict):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(entry) + '\n')


def _save_state(state: dict):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding='utf-8')


def _fetch_quote(address: str):
    if not address:
        return None
    data = sol_module._fetch_token_overview(address)
    price = data.get('price') if isinstance(data, dict) else None
    liquidity = data.get('liquidity') if isinstance(data, dict) else None
    volume = data.get('volume_24h_usd') if isinstance(data, dict) else None
    return {
        'price': price,
        'liquidity_usd': liquidity,
        'volume_24h_usd': volume
    }


def main():
    positions = _load_json(OPEN_POSITIONS_PATH, [])
    if not positions:
        return
    state = _load_json(STATE_PATH, {})
    updated = False
    for position in positions:
        address = position.get('address')
        entry_time = position.get('entry_time')
        if not address or not entry_time:
            continue
        state_key = f"{address}|{entry_time}"
        if state.get(state_key):
            continue
        quote = _fetch_quote(address)
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        log_entry = {
            'timestamp': timestamp,
            'token': position.get('token'),
            'address': address,
            'entry_time': entry_time,
            'entry_price_paper': position.get('entry_price'),
            'position_size_usd': position.get('position_size_usd'),
            'quote_price': None if not quote else quote.get('price'),
            'liquidity_usd': None if not quote else quote.get('liquidity_usd'),
            'volume_24h_usd': None if not quote else quote.get('volume_24h_usd'),
            'source': 'birdeye'
        }
        _append_log(log_entry)
        state[state_key] = {
            'logged_at': timestamp,
            'quote_price': log_entry['quote_price']
        }
        updated = True
    if updated:
        _save_state(state)


if __name__ == '__main__':
    main()
