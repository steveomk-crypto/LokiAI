#!/usr/bin/env python3
"""Fetch CoinDesk RSS headlines as an alternative to CryptoCompare news."""

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from api_usage import log_api_call

RSS_URL = "https://www.coindesk.com/arc/outboundfeeds/rss/"
CACHE_PATH = Path("/data/.openclaw/workspace/cache/coindesk_news.json")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def fetch_rss(limit: int = 10):
    try:
        req = Request(RSS_URL, headers={'User-Agent': 'openclaw-news'})
        with urlopen(req, timeout=15) as resp:
            log_api_call('coindesk')
            xml_data = resp.read()
    except (HTTPError, URLError):
        return []
    root = ET.fromstring(xml_data)
    channel = root.find('channel')
    if channel is None:
        return []
    items = []
    for item in channel.findall('item')[:limit]:
        items.append({
            'title': (item.findtext('title') or '').strip(),
            'link': (item.findtext('link') or '').strip(),
            'pubDate': item.findtext('pubDate'),
            'description': (item.findtext('description') or '').strip()
        })
    return items


def save_snapshot(records):
    snapshot = {
        'source': 'CoinDesk RSS',
        'fetched_at': _utc_now(),
        'count': len(records),
        'articles': records
    }
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(snapshot, indent=2), encoding='utf-8')
    return snapshot


def main():
    parser = argparse.ArgumentParser(description='Fetch CoinDesk RSS headlines')
    parser.add_argument('--limit', type=int, default=10, help='Number of articles to keep')
    args = parser.parse_args()

    articles = fetch_rss(limit=args.limit)
    snapshot = save_snapshot(articles)
    print(json.dumps({
        'fetched_at': snapshot['fetched_at'],
        'count': snapshot['count'],
        'sample_titles': [a['title'] for a in snapshot['articles'][:3]]
    }, indent=2))


if __name__ == '__main__':
    raise SystemExit(main())
