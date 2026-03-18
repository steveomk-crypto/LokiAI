#!/usr/bin/env python3
"""Utility to pull Binance order books and recent trades for USDT pairs."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from api_usage import log_api_call

BASE_URL = "https://api.binance.com/api/v3"
CACHE_DIR = Path("/data/.openclaw/workspace/cache/binance_liquidity")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _fetch(endpoint: str, params: Dict[str, Any]):
    query = urlencode(params)
    url = f"{BASE_URL}/{endpoint}?{query}"
    try:
        with urlopen(url, timeout=10) as resp:
            log_api_call('binance')
            return json.load(resp)
    except (HTTPError, URLError, json.JSONDecodeError):
        return None


def fetch_order_book(symbol: str, limit: int = 50):
    return _fetch('depth', {'symbol': symbol, 'limit': limit})


def fetch_recent_trades(symbol: str, limit: int = 50):
    return _fetch('trades', {'symbol': symbol, 'limit': limit})


def save_snapshot(symbol: str, order_book: Dict, trades: Dict):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        'symbol': symbol,
        'fetched_at': _utc_now(),
        'order_book': order_book,
        'recent_trades': trades
    }
    path = CACHE_DIR / f"{symbol}.json"
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    return path


def main():
    parser = argparse.ArgumentParser(description='Fetch Binance order book + trades for a USDT pair')
    parser.add_argument('--symbol', default='BTC', help='Base asset symbol (defaults to BTC, pairs with USDT)')
    parser.add_argument('--depth', type=int, default=50, help='Order book depth (max 500)')
    parser.add_argument('--trades', type=int, default=50, help='Number of recent trades (max 1000)')
    args = parser.parse_args()

    pair = f"{args.symbol.upper()}USDT"
    order_book = fetch_order_book(pair, limit=args.depth)
    trades = fetch_recent_trades(pair, limit=args.trades)
    if not order_book and not trades:
        print(f"Failed to fetch data for {pair}")
        return 1
    snapshot_path = save_snapshot(pair, order_book, trades)
    print(json.dumps({
        'symbol': pair,
        'order_book_levels': len(order_book.get('bids', [])) if order_book else 0,
        'recent_trades': len(trades) if trades else 0,
        'cache_path': str(snapshot_path)
    }, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
