#!/usr/bin/env python3
"""Lightweight GitHub repository inspector (stats + open issues)."""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from api_usage import log_api_call

API_BASE = "https://api.github.com"
CACHE_DIR = Path("/data/.openclaw/workspace/cache/github_inspector")
TOKEN = os.environ.get('GITHUB_TOKEN')


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _fetch(endpoint: str):
    url = f"{API_BASE}{endpoint}"
    headers = {'User-Agent': 'openclaw-bot'}
    if TOKEN:
        headers['Authorization'] = f"Bearer {TOKEN}"
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=15) as resp:
            log_api_call('github')
            return json.load(resp)
    except (HTTPError, URLError, json.JSONDecodeError):
        return None


def inspect_repo(owner: str, repo: str) -> Dict[str, Any]:
    meta = _fetch(f"/repos/{owner}/{repo}") or {}
    issues = _fetch(f"/repos/{owner}/{repo}/issues?state=open&per_page=5") or []
    payload = {
        'repo': f"{owner}/{repo}",
        'fetched_at': _utc_now(),
        'meta': {
            'description': meta.get('description'),
            'stars': meta.get('stargazers_count'),
            'forks': meta.get('forks_count'),
            'open_issues': meta.get('open_issues_count'),
            'default_branch': meta.get('default_branch'),
            'pushed_at': meta.get('pushed_at')
        },
        'top_issues': [
            {
                'number': issue.get('number'),
                'title': issue.get('title'),
                'user': issue.get('user', {}).get('login'),
                'url': issue.get('html_url')
            }
            for issue in issues if 'pull_request' not in issue
        ]
    }
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{owner}_{repo}.json"
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    payload['cache_path'] = str(path)
    return payload


def main():
    parser = argparse.ArgumentParser(description='Summarize a GitHub repository via the REST API')
    parser.add_argument('repo', help='Repository in owner/repo format (e.g., openclaw/openclaw)')
    args = parser.parse_args()

    owner, repo = args.repo.split('/', 1)
    payload = inspect_repo(owner, repo)
    print(json.dumps(payload, indent=2))


if __name__ == '__main__':
    raise SystemExit(main())
