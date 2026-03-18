#!/usr/bin/env python3
"""Fetch CryptoCompare news headlines and sentiment."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from api_usage import log_api_call

NEWS_URL = "https://min-api.cryptocompare.com/data/v2/news/"
CACHE_PATH = Path("/data/.openclaw/workspace/cache/cryptocompare_news.json")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def fetch_news(params: Dict[str, Any]):
    query = urlencode(params)
    url = f"{NEWS_URL}?{query}"
    try:
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(req, timeout=15) as resp:
            log_api_call('cryptocompare')
            payload = json.load(resp)
            return payload.get('Data', [])
    except (HTTPError, URLError, json.JSONDecodeError):
        return []


def save_snapshot(records):
    snapshot = {
        'fetched_at': _utc_now(),
        'count': len(records),
        'articles': records
    }
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(snapshot, indent=2), encoding='utf-8')
    return snapshot


def main():
    parser = argparse.ArgumentParser(description='Pull CryptoCompare news headlines and sentiment')
    parser.add_argument('--categories', default='BTC,ETH,TRADING', help='Comma-separated categories')
    parser.add_argument('--limit', type=int, default=10, help='Number of articles to fetch')
    args = parser.parse_args()

    params = {
        'lang': 'EN',
        'categories': args.categories,
        'lTs': 0,
        'sortOrder': 'latest',
        'limit': args.limit
    }
    articles = fetch_news(params)
    if not isinstance(articles, list):
        articles = []
    snapshot = save_snapshot(articles)
    print(json.dumps({
        'fetched_at': snapshot['fetched_at'],
        'count': snapshot['count'],
        'sample_titles': [item.get('title') for item in snapshot['articles'][:3]]
    }, indent=2))


if __name__ == '__main__':
    raise SystemExit(main())
