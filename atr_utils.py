import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from api_usage import log_api_call

ATR_CACHE_PATH = Path('/data/.openclaw/workspace/cache/atr_cache.json')
ATR_REFRESH_MINUTES = 15
COINGECKO_OHLC_URL = "https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc?vs_currency=usd&days=1"


def _load_cache() -> Dict:
    if not ATR_CACHE_PATH.exists():
        return {}
    try:
        return json.loads(ATR_CACHE_PATH.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_cache(cache: Dict) -> None:
    ATR_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    ATR_CACHE_PATH.write_text(json.dumps(cache, indent=2), encoding='utf-8')


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _is_fresh(entry: Dict, refresh_minutes: int) -> bool:
    fetched_at = entry.get('fetched_at')
    if not fetched_at:
        return False
    try:
        fetched_dt = datetime.fromisoformat(fetched_at.replace('Z', '+00:00'))
    except ValueError:
        return False
    return (_utcnow() - fetched_dt) < timedelta(minutes=refresh_minutes)


def _fetch_ohlc_series(coin_id: str) -> Optional[list]:
    if not coin_id:
        return None
    url = COINGECKO_OHLC_URL.format(coin_id=coin_id)
    try:
        with urlopen(url) as resp:
            log_api_call('coingecko')
            data = json.load(resp)
            return data if isinstance(data, list) else None
    except (URLError, HTTPError, json.JSONDecodeError):
        return None


def _compute_atr_from_series(series: list, period: int = 14) -> Optional[Dict[str, float]]:
    if not series or len(series) < 2:
        return None
    ohlc = []
    for row in series:
        if not isinstance(row, list) or len(row) < 5:
            continue
        try:
            high = float(row[2])
            low = float(row[3])
            close = float(row[4])
        except (TypeError, ValueError):
            continue
        ohlc.append((high, low, close))
    if len(ohlc) < 2:
        return None
    true_ranges = []
    prev_close = ohlc[0][2]
    for high, low, close in ohlc[1:]:
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        true_ranges.append(tr)
        prev_close = close
    if not true_ranges:
        return None
    period = min(period, len(true_ranges))
    atr = sum(true_ranges[-period:]) / period
    last_close = prev_close
    return {
        'atr_usd': atr,
        'last_close': last_close
    }


def get_atr_for_symbol(symbol: str, meta: Optional[Dict], refresh_minutes: int = ATR_REFRESH_MINUTES) -> Optional[Dict]:
    if not meta:
        return None
    coin_id = meta.get('id')
    if not coin_id:
        return None
    cache = _load_cache()
    entry = cache.get(coin_id)
    if entry and _is_fresh(entry, refresh_minutes):
        return entry
    series = _fetch_ohlc_series(coin_id)
    if not series:
        return entry  # fall back to stale data if available
    atr_info = _compute_atr_from_series(series)
    if not atr_info:
        return entry
    atr_usd = atr_info['atr_usd']
    last_close = atr_info['last_close'] or 0.0
    if atr_usd <= 0 or last_close <= 0:
        return entry
    payload = {
        'coin_id': coin_id,
        'symbol': symbol,
        'atr_usd': round(atr_usd, 6),
        'atr_pct': round(atr_usd / last_close, 6),
        'fetched_at': _utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
        'source': 'coingecko'
    }
    cache[coin_id] = payload
    _save_cache(cache)
    return payload
