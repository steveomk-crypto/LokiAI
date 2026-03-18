#!/usr/bin/env python3
"""CoinPaprika validation feed: map symbols to IDs and pull ticker stats."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from api_usage import log_api_call

COIN_INDEX_URL = "https://api.coinpaprika.com/v1/coins"
TICKER_URL = "https://api.coinpaprika.com/v1/tickers/{coin_id}"
INDEX_CACHE = Path("/data/.openclaw/workspace/cache/coinpaprika_coins.json")
SNAPSHOT_PATH = Path("/data/.openclaw/workspace/cache/coinpaprika_validation.json")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _fetch_json(url: str):
    try:
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(req, timeout=15) as resp:
            log_api_call('coinpaprika')
            return json.load(resp)
    except (HTTPError, URLError, json.JSONDecodeError):
        return None


def _load_index(force: bool = False) -> Dict[str, str]:
    if INDEX_CACHE.exists() and not force:
        try:
            data = json.loads(INDEX_CACHE.read_text(encoding='utf-8'))
            return {item['symbol'].upper(): item['id'] for item in data if 'symbol' in item and 'id' in item}
        except (json.JSONDecodeError, KeyError):
            pass
    data = _fetch_json(COIN_INDEX_URL) or []
    if isinstance(data, list):
        data.sort(key=lambda item: (0 if item.get('rank') else 1, float(item.get('rank') or 'inf')))
        INDEX_CACHE.parent.mkdir(parents=True, exist_ok=True)
        INDEX_CACHE.write_text(json.dumps(data), encoding='utf-8')
        mapping = {}
        for item in data:
            symbol = (item.get('symbol') or '').upper()
            coin_id = item.get('id')
            if not symbol or not coin_id or not item.get('is_active'):
                continue
            mapping.setdefault(symbol, coin_id)
        return mapping
    return {}


def fetch_ticker(coin_id: str) -> Optional[Dict]:
    if not coin_id:
        return None
    return _fetch_json(TICKER_URL.format(coin_id=coin_id))


def validate_symbols(symbols: List[str]) -> Dict[str, Dict]:
    index = _load_index()
    results: Dict[str, Dict] = {}
    for sym in symbols:
        key = sym.upper()
        coin_id = index.get(key)
        ticker = fetch_ticker(coin_id) if coin_id else None
        if ticker:
            results[key] = {
                'coin_id': coin_id,
                'price_usd': ticker.get('quotes', {}).get('USD', {}).get('price'),
                'volume_24h': ticker.get('quotes', {}).get('USD', {}).get('volume_24h'),
                'percent_change_24h': ticker.get('quotes', {}).get('USD', {}).get('percent_change_24h'),
                'market_cap': ticker.get('quotes', {}).get('USD', {}).get('market_cap')
            }
        else:
            results[key] = {'coin_id': coin_id, 'error': 'not_found'}
    snapshot = {
        'symbols': symbols,
        'fetched_at': _utc_now(),
        'results': results
    }
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.write_text(json.dumps(snapshot, indent=2), encoding='utf-8')
    return snapshot


def main():
    parser = argparse.ArgumentParser(description='Validate token data via CoinPaprika tickers')
    parser.add_argument('symbols', nargs='*', default=['BTC', 'ETH'], help='Symbols to validate')
    parser.add_argument('--refresh-index', action='store_true', help='Force refresh of the coin index cache')
    args = parser.parse_args()

    if args.refresh_index:
        _load_index(force=True)
    snapshot = validate_symbols(args.symbols)
    print(json.dumps(snapshot, indent=2))


if __name__ == '__main__':
    raise SystemExit(main())
