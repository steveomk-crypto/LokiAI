#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path('/home/lokiai/.openclaw/workspace')
CACHE = WORKSPACE / 'cache'
OUT_PATH = CACHE / 'social_intel_pulse.json'
COINDESK_PATH = CACHE / 'coindesk_news.json'
MARKET_STATE_PATH = CACHE / 'market_state.json'
WS_STATE_PATH = CACHE / 'coinbase_ws_state.json'


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_narrative_item(market_state: dict) -> dict | None:
    top = market_state.get('top_opportunities') or []
    if not top:
        return None
    tokens = [item.get('token') for item in top[:3] if item.get('token')]
    if not tokens:
        return None
    mode = market_state.get('mode', 'baseline')
    momentum = top[0].get('momentum', 0)
    return {
        'timestamp': market_state.get('computed_at') or now_iso(),
        'category': 'narrative',
        'headline': f"Scanner focus narrowing to {', '.join(tokens[:3])}",
        'source': 'internal synthesis',
        'symbol_scope': tokens,
        'importance': 'medium',
        'market_implication': f"Mode is {mode}; only the strongest Coinbase-actionable names are surviving the intake filter. Top momentum lead is {tokens[0]} at {momentum:.1f}%.",
        'confidence': 'medium',
        'actionability': 'monitor',
    }


def build_ws_item(ws_state: dict) -> dict:
    connected = bool(ws_state.get('connected'))
    last_message_at = ws_state.get('last_message_at')
    status = 'online' if connected else 'offline'
    return {
        'timestamp': now_iso(),
        'category': 'exchange',
        'headline': f"Coinbase Websocket {status}",
        'source': 'internal telemetry',
        'symbol_scope': ['Coinbase'],
        'importance': 'high' if connected else 'critical',
        'market_implication': f"Live Coinbase market state is {'available' if connected else 'degraded'}; last message at {last_message_at or 'unknown'}.",
        'confidence': 'high',
        'actionability': 'observe' if connected else 'monitor',
    }


def build_news_items(news_payload: dict) -> list[dict]:
    items = []
    for article in (news_payload.get('articles') or [])[:3]:
        title = article.get('title') or 'Untitled'
        lower = title.lower()
        category = 'macro'
        importance = 'medium'
        symbol_scope = []
        if 'coinbase' in lower or 'listing' in lower or 'exchange' in lower:
            category = 'exchange'
            importance = 'high'
            symbol_scope = ['Coinbase']
        elif any(word in lower for word in ['sec', 'cftc', 'regulator', 'policy', 'etf']):
            category = 'regulatory'
            importance = 'high'
        elif any(word in lower for word in ['bitcoin', 'solana', 'ai', 'wallet']):
            category = 'narrative'
        items.append({
            'timestamp': article.get('pubDate') or news_payload.get('fetched_at') or now_iso(),
            'category': category,
            'headline': title,
            'source': news_payload.get('source', 'news feed'),
            'symbol_scope': symbol_scope,
            'importance': importance,
            'market_implication': (article.get('description') or 'Potential market relevance detected.')[:220],
            'confidence': 'medium',
            'actionability': 'monitor',
        })
    return items


def main() -> int:
    market_state = load_json(MARKET_STATE_PATH, {})
    ws_state = load_json(WS_STATE_PATH, {})
    coindesk = load_json(COINDESK_PATH, {})

    items = []
    narrative = build_narrative_item(market_state)
    if narrative:
        items.append(narrative)
    items.append(build_ws_item(ws_state))
    items.extend(build_news_items(coindesk))

    payload = {
        'updated_at': now_iso(),
        'items': items[:5],
    }
    OUT_PATH.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
