#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib import parse, request, error

WORKSPACE = Path('/home/lokiai/.openclaw/workspace')
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from scripts.telegram_lanes import resolve_lane_target


def load_token() -> str:
    env_path = WORKSPACE / 'secrets' / 'telegram_bot.env'
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
    if token:
        return token
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('export '):
                line = line.split('export ', 1)[1]
            if '=' not in line:
                continue
            k, v = line.split('=', 1)
            if k.strip() == 'TELEGRAM_BOT_TOKEN':
                return v.strip().strip('"').strip("'")
    raise RuntimeError('TELEGRAM_BOT_TOKEN not found')


def send_lane_message(lane: str, text: str) -> dict:
    token = load_token()
    chat_id, thread_id = resolve_lane_target(lane)
    if not chat_id:
        raise RuntimeError(f'Lane {lane} has no chatId configured')
    payload = {'chat_id': chat_id, 'text': text}
    if thread_id:
        payload['message_thread_id'] = thread_id
    data = parse.urlencode(payload).encode('utf-8')
    req = request.Request(f'https://api.telegram.org/bot{token}/sendMessage', data=data)
    try:
        with request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except error.HTTPError as http_err:
        detail = http_err.read().decode('utf-8', errors='ignore')
        raise RuntimeError(f'Telegram API error {http_err.code}: {detail}') from http_err


if __name__ == '__main__':
    lane = sys.argv[1] if len(sys.argv) > 1 else 'ops'
    text = sys.argv[2] if len(sys.argv) > 2 else f'LokiAI test: {lane} lane probe ✅'
    result = send_lane_message(lane, text)
    print(json.dumps(result, indent=2))
