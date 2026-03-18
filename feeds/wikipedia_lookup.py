#!/usr/bin/env python3
"""Fetch concise Wikipedia summaries for research context."""

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import quote
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from api_usage import log_api_call

API_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{slug}"
CACHE_DIR = Path("/data/.openclaw/workspace/cache/wikipedia")


def fetch_summary(topic: str):
    slug = quote(topic.strip().replace(' ', '_'))
    url = API_URL.format(slug=slug)
    try:
        req = Request(url, headers={'User-Agent': 'openclaw-research'})
        with urlopen(req, timeout=10) as resp:
            log_api_call('wikipedia')
            return json.load(resp)
    except (HTTPError, URLError, json.JSONDecodeError):
        return None


def cache_summary(topic: str, payload):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    slug = topic.strip().replace(' ', '_')
    path = CACHE_DIR / f"{slug}.json"
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    return path


def main():
    parser = argparse.ArgumentParser(description='Lookup a Wikipedia page summary')
    parser.add_argument('topic', help='Topic title, e.g., "Binance" or "Momentum trading"')
    args = parser.parse_args()

    data = fetch_summary(args.topic)
    if not data or data.get('type') == 'https://mediawiki.org/wiki/HyperSwitch/errors/not_found':
        print(json.dumps({'topic': args.topic, 'status': 'not_found'}))
        return 1
    cache_path = cache_summary(args.topic, data)
    print(json.dumps({
        'topic': args.topic,
        'title': data.get('title'),
        'description': data.get('description'),
        'extract': data.get('extract'),
        'cache_path': str(cache_path)
    }, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
