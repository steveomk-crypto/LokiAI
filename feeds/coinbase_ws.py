#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
import websockets

WORKSPACE = Path('/home/lokiai/.openclaw/workspace')
CACHE_DIR = WORKSPACE / 'cache'
MARKET_LOG_DIR = WORKSPACE / 'market_logs' / 'coinbase_ws'
SYSTEM_LOG_DIR = WORKSPACE / 'system_logs'

STATE_PATH = CACHE_DIR / 'coinbase_ws_state.json'
PRODUCTS_PATH = CACHE_DIR / 'coinbase_products.json'
TICKERS_PATH = CACHE_DIR / 'coinbase_tickers.json'
PID_PATH = SYSTEM_LOG_DIR / 'coinbase_ws.pid'

COINBASE_PRODUCTS_URL = 'https://api.exchange.coinbase.com/products'
COINBASE_WS_URL = 'wss://ws-feed.exchange.coinbase.com'
QUOTE_ALLOWLIST = {'USD', 'USDC', 'USDT'}
PREFERRED_BASES = {
    'BTC', 'ETH', 'SOL', 'XRP', 'ADA', 'DOGE', 'AVAX', 'LINK', 'LTC', 'BCH',
    'UNI', 'AAVE', 'NEAR', 'INJ', 'ATOM', 'APT', 'SUI', 'ARB', 'OP', 'BONK',
    'PEPE', 'FET', 'RNDR', 'ONDO', 'TIA', 'SEI', 'IMX', 'JUP', 'WIF', 'PYTH',
    'TRIA', 'DIMO', 'THQ', 'REZ', 'ZRO', 'GRT', 'AKT', 'AERO', 'ANKR', 'AIOZ',
}
DEFAULT_PRODUCT_LIMIT = 80
FLUSH_SECONDS = 60
SNAPSHOT_TOP_N = 25


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def atomic_json_write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=False))
    tmp.replace(path)


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as fh:
        fh.write(json.dumps(payload, sort_keys=False) + '\n')


@dataclass
class ProductState:
    product_id: str
    base_currency: str
    quote_currency: str
    status: str
    price: float | None = None
    volume_24h: float | None = None
    best_bid: float | None = None
    best_ask: float | None = None
    last_update: str | None = None
    sequence: int | None = None
    price_points: deque[tuple[float, float]] = field(default_factory=lambda: deque(maxlen=400))

    def update_from_ticker(self, msg: dict[str, Any], ts: float) -> None:
        self.price = _to_float(msg.get('price'))
        self.volume_24h = _to_float(msg.get('volume_24h'))
        self.best_bid = _to_float(msg.get('best_bid'))
        self.best_ask = _to_float(msg.get('best_ask'))
        self.sequence = msg.get('sequence')
        self.last_update = msg.get('time') or now_iso()
        if self.price is not None:
            self.price_points.append((ts, self.price))

    def drift(self, lookback_seconds: int) -> float | None:
        if self.price is None or not self.price_points:
            return None
        cutoff = time.time() - lookback_seconds
        candidate = None
        for ts, price in self.price_points:
            if ts >= cutoff:
                candidate = price
                break
        if candidate in (None, 0):
            return None
        return round(((self.price - candidate) / candidate) * 100, 4)

    def freshness_seconds(self) -> float | None:
        if not self.last_update:
            return None
        try:
            dt = datetime.fromisoformat(self.last_update.replace('Z', '+00:00'))
            return round(time.time() - dt.timestamp(), 2)
        except Exception:
            return None

    def to_dict(self) -> dict[str, Any]:
        return {
            'product_id': self.product_id,
            'base_currency': self.base_currency,
            'quote_currency': self.quote_currency,
            'status': self.status,
            'price': self.price,
            'volume_24h': self.volume_24h,
            'best_bid': self.best_bid,
            'best_ask': self.best_ask,
            'last_update': self.last_update,
            'sequence': self.sequence,
            'drift_60s': self.drift(60),
            'drift_300s': self.drift(300),
            'drift_900s': self.drift(900),
            'freshness_seconds': self.freshness_seconds(),
        }


def _to_float(value: Any) -> float | None:
    try:
        if value in (None, ''):
            return None
        return float(value)
    except Exception:
        return None


class CoinbaseWSService:
    def __init__(self, product_limit: int = DEFAULT_PRODUCT_LIMIT, flush_seconds: int = FLUSH_SECONDS) -> None:
        self.product_limit = product_limit
        self.flush_seconds = flush_seconds
        self.started_at = now_iso()
        self.last_message_at: str | None = None
        self.last_flush_at: str | None = None
        self.connected = False
        self.messages_received = 0
        self.reconnect_count = 0
        self.last_error: str | None = None
        self.last_disconnect_at: str | None = None
        self.products_meta: list[dict[str, Any]] = []
        self.products: dict[str, ProductState] = {}

    def bootstrap_products(self) -> None:
        response = requests.get(COINBASE_PRODUCTS_URL, timeout=30)
        response.raise_for_status()
        products = response.json()
        filtered = []
        for p in products:
            if p.get('quote_currency') not in QUOTE_ALLOWLIST:
                continue
            if p.get('status') != 'online':
                continue
            if p.get('trading_disabled'):
                continue
            base = p.get('base_currency')
            if not base:
                continue
            product = {
                'product_id': p['id'],
                'base_currency': base,
                'quote_currency': p['quote_currency'],
                'status': p['status'],
                'base_increment': p.get('base_increment'),
                'quote_increment': p.get('quote_increment'),
                'min_market_funds': p.get('min_market_funds'),
                'auction_mode': p.get('auction_mode', False),
                'preferred': base in PREFERRED_BASES,
            }
            filtered.append(product)

        preferred = [p for p in filtered if p['preferred']]
        preferred.sort(key=lambda x: (x['quote_currency'], x['base_currency']))

        if len(preferred) >= self.product_limit:
            selected = preferred[: self.product_limit]
        else:
            fallback = [p for p in filtered if not p['preferred'] and p['quote_currency'] == 'USD']
            fallback.sort(key=lambda x: (x['quote_currency'], x['base_currency']))
            selected = preferred + fallback[: max(0, self.product_limit - len(preferred))]

        self.products_meta = selected[: self.product_limit]
        self.products = {}
        for p in self.products_meta:
            self.products[p['product_id']] = ProductState(**{k: p[k] for k in ('product_id', 'base_currency', 'quote_currency', 'status')})
        atomic_json_write(PRODUCTS_PATH, self.products_meta)

    async def run_forever(self) -> None:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        MARKET_LOG_DIR.mkdir(parents=True, exist_ok=True)
        SYSTEM_LOG_DIR.mkdir(parents=True, exist_ok=True)
        PID_PATH.write_text(str(os.getpid()))
        self.bootstrap_products()

        while True:
            try:
                await self._run_once()
            except asyncio.CancelledError:
                self.connected = False
                self.last_disconnect_at = now_iso()
                self.last_error = 'service_cancelled'
                self._write_state(extra={'status': 'stopped'})
                raise
            except Exception as exc:
                self.connected = False
                self.reconnect_count += 1
                self.last_disconnect_at = now_iso()
                self.last_error = str(exc)
                self._write_state(extra={'status': 'reconnecting'})
                await asyncio.sleep(min(30, 2 + self.reconnect_count))

    async def _run_once(self) -> None:
        product_ids = [p['product_id'] for p in self.products_meta]
        flush_task = None
        try:
            async with websockets.connect(COINBASE_WS_URL, ping_interval=20, ping_timeout=20, max_size=2_000_000) as ws:
                self.connected = True
                self.last_error = None
                self._write_state(extra={'status': 'connected'})
                subscribe_message = {
                    'type': 'subscribe',
                    'product_ids': product_ids,
                    'channels': ['ticker', 'heartbeat'],
                }
                await ws.send(json.dumps(subscribe_message))
                try:
                    first_message = await asyncio.wait_for(ws.recv(), timeout=10)
                    first_payload = json.loads(first_message)
                    self.messages_received += 1
                    self.last_message_at = now_iso()
                    if first_payload.get('type') == 'ticker':
                        product_id = first_payload.get('product_id')
                        state = self.products.get(product_id)
                        if state:
                            state.update_from_ticker(first_payload, time.time())
                except asyncio.TimeoutError:
                    pass
                flush_task = asyncio.create_task(self._periodic_flush())
                async for raw in ws:
                    msg = json.loads(raw)
                    self.messages_received += 1
                    self.last_message_at = now_iso()
                    msg_type = msg.get('type')
                    if msg_type == 'ticker':
                        product_id = msg.get('product_id')
                        state = self.products.get(product_id)
                        if state:
                            state.update_from_ticker(msg, time.time())
                    elif msg_type == 'error':
                        raise RuntimeError(f"Coinbase WS error: {msg}")
        except asyncio.CancelledError:
            self.connected = False
            self.last_disconnect_at = now_iso()
            self.last_error = 'run_once_cancelled'
            self._write_state(extra={'status': 'stopped'})
            raise
        except Exception as exc:
            self.connected = False
            self.last_disconnect_at = now_iso()
            self.last_error = str(exc)
            self._write_state(extra={'status': 'reconnecting'})
            raise
        finally:
            if flush_task:
                flush_task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await flush_task
            self.connected = False
            if self.last_disconnect_at is None:
                self.last_disconnect_at = now_iso()
            self._write_state(extra={'status': 'disconnected' if not self.last_error else 'reconnecting'})

    async def _periodic_flush(self) -> None:
        while True:
            self.flush_to_disk()
            await asyncio.sleep(self.flush_seconds)

    def flush_to_disk(self) -> None:
        tickers = {product_id: state.to_dict() for product_id, state in self.products.items()}
        atomic_json_write(TICKERS_PATH, tickers)
        snapshot_ts = now_iso()
        ranked = sorted(
            [v for v in tickers.values() if v.get('price') is not None],
            key=lambda x: abs(x.get('drift_300s') or 0),
            reverse=True,
        )[:SNAPSHOT_TOP_N]
        append_jsonl(
            MARKET_LOG_DIR / f"{datetime.now().date().isoformat()}.jsonl",
            {
                'timestamp': snapshot_ts,
                'connected': self.connected,
                'messages_received': self.messages_received,
                'tracked_products': len(self.products),
                'top_movers': ranked,
            },
        )
        self.last_flush_at = snapshot_ts
        self._write_state()

    def _write_state(self, extra: dict[str, Any] | None = None) -> None:
        payload = {
            'status': 'connected' if self.connected else 'disconnected',
            'connected': self.connected,
            'started_at': self.started_at,
            'last_message_at': self.last_message_at,
            'last_flush_at': self.last_flush_at,
            'last_disconnect_at': self.last_disconnect_at,
            'last_error': self.last_error,
            'tracked_products': len(self.products),
            'messages_received': self.messages_received,
            'reconnect_count': self.reconnect_count,
        }
        if extra:
            payload.update(extra)
        atomic_json_write(STATE_PATH, payload)


async def main() -> None:
    service = CoinbaseWSService(
        product_limit=int(os.getenv('COINBASE_WS_PRODUCT_LIMIT', DEFAULT_PRODUCT_LIMIT)),
        flush_seconds=int(os.getenv('COINBASE_WS_FLUSH_SECONDS', FLUSH_SECONDS)),
    )
    await service.run_forever()


if __name__ == '__main__':
    import contextlib
    asyncio.run(main())
