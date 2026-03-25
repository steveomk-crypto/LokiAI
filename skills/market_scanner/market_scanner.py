import json
import os
import sys
from collections import defaultdict, OrderedDict
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from strategy_config import get_strategy_value

HIGH_VOLUME_LEVEL = 75000   # USD volume threshold
HIGH_MOMENTUM_LEVEL = get_strategy_value("momentum_threshold")
RUN_LOOKBACK = 5            # Number of prior runs to compare
MIN_PERSISTENCE_FOR_PRIORITY = 2
STRONG_VOLUME_FLOOR = 5_000_000
HIGH_CONVICTION_SCORE_FLOOR = 0.45
timestamp_format = "%Y-%m-%dT%H:%M"

LOG_DIR = '/home/lokiai/.openclaw/workspace/market_logs/'
DEX_API_URL = 'https://api.dexscreener.com/latest/dex/pairs'
CANDIDATE_PATH = '/home/lokiai/.openclaw/workspace/market_scanner/candidates.json'
MARKET_STATE_PATH = '/home/lokiai/.openclaw/workspace/cache/market_state.json'
COINBASE_PRODUCTS_PATH = '/home/lokiai/.openclaw/workspace/cache/coinbase_products.json'
HELIUS_SECRET_PATH = '/home/lokiai/.openclaw/workspace/secrets/helius_api_credentials.env'


def _load_env_from_file(path):
    if not os.path.exists(path):
        return {}
    data = {}
    with open(path, 'r') as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith('#') or '=' not in stripped:
                continue
            key, value = stripped.split('=', 1)
            data[key.strip()] = value.strip()
    return data


HELIUS_API_KEY = os.environ.get('HELIUS_API_KEY') or _load_env_from_file(HELIUS_SECRET_PATH).get('HELIUS_API_KEY')
HELIUS_RPC_URL = f"https://rpc.helius.xyz/?api-key={HELIUS_API_KEY}" if HELIUS_API_KEY else None


def _parse_legacy_line(line: str):
    parts = line.split('|')
    if len(parts) < 2:
        raise ValueError('Malformed legacy line')
    entry = {
        'timestamp': parts[0],
        'token': parts[1],
        'volume': None,
        'momentum': None,
        'status': parts[2] if len(parts) > 2 else 'signal'
    }
    return entry


def _load_recent_runs(log_path: str, max_runs: int):
    if not os.path.exists(log_path):
        return OrderedDict()

    entries = []
    with open(log_path, 'r') as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            if line.startswith('{'):
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            else:
                try:
                    entries.append(_parse_legacy_line(line))
                except ValueError:
                    continue

    entries.sort(key=lambda e: e.get('timestamp', ''))
    runs = OrderedDict()
    for entry in entries:
        ts = entry.get('timestamp')
        if not ts:
            continue
        runs.setdefault(ts, []).append(entry)

    if len(runs) <= max_runs:
        return runs

    trimmed_keys = list(runs.keys())[-max_runs:]
    return OrderedDict((k, runs[k]) for k in trimmed_keys)


def _build_history(runs):
    history = defaultdict(list)
    for ts, entries in runs.items():
        for entry in entries:
            history[entry.get('token')].append(entry)
    return history


def _normalize(value, max_value):
    if not max_value:
        return 0
    return value / max_value


def _scale_positive_ratio(value, cap=2.0):
    if value is None:
        return 0.5
    value = max(min(value, cap), 0)
    return value / cap


def _scale_signed_ratio(value, cap=1.0):
    if value is None:
        return 0.5
    value = max(min(value, cap), -cap)
    return (value / cap + 1) / 2


from urllib.request import Request
from datetime import timedelta


def _momentum_delta(prev_entries, cutoff_minutes, current_dt):
    cutoff = current_dt - timedelta(minutes=cutoff_minutes)
    target = None
    for entry in reversed(prev_entries):
        ts = entry.get('timestamp')
        if not ts:
            continue
        try:
            dt = datetime.strptime(ts, timestamp_format)
        except ValueError:
            continue
        if dt <= cutoff:
            momentum = entry.get('momentum')
            if momentum is not None:
                target = float(momentum)
                break
    return target


def _compute_alignment(current_momentum, prev_entries, current_dt):
    m5_ref = _momentum_delta(prev_entries, 5, current_dt)
    m15_ref = _momentum_delta(prev_entries, 15, current_dt)
    m60_ref = _momentum_delta(prev_entries, 60, current_dt)

    def delta(value):
        if value is None:
            return None
        return current_momentum - value

    m5 = delta(m5_ref)
    m15 = delta(m15_ref)
    m60 = delta(m60_ref)

    components = []
    for val, cap in ((m5, 5.0), (m15, 5.0), (m60, 5.0)):
        if val is not None:
            components.append(_scale_signed_ratio(val, cap))
    alignment = sum(components) / len(components) if components else 0.5

    trend = 'unknown'
    positives = [val for val in (m5, m15, m60) if val is not None and val > 0]
    negatives = [val for val in (m5, m15, m60) if val is not None and val < 0]

    if all(val is not None for val in (m5, m15, m60)):
        if m5 > 0 and m15 > 0 and m60 > 0:
            if m5 >= m15 >= m60 and (m5 - m15 > 0.3 or m15 - m60 > 0.3):
                trend = 'accelerating'
            else:
                trend = 'steady'
        elif m5 > 0 and (m15 <= 0 or m60 <= 0):
            trend = 'isolated spike'
        else:
            trend = 'fading'
    elif m5 is not None and m5 > 0 and (m15 is None or m15 <= 0 or m60 is None or m60 <= 0):
        trend = 'isolated spike'
    elif m5 is not None and m15 is not None and m5 < m15:
        trend = 'fading'
    else:
        trend = 'steady'

    if trend == 'accelerating':
        alignment = min(alignment + 0.1, 1.0)
    elif trend == 'isolated spike':
        alignment = max(alignment - 0.2, 0.0)
    elif trend == 'fading':
        alignment = max(alignment - 0.1, 0.0)

    return {
        'momentum_5m': None if m5 is None else round(m5, 6),
        'momentum_15m': None if m15 is None else round(m15, 6),
        'momentum_60m': None if m60 is None else round(m60, 6),
        'alignment': round(alignment, 6),
        'trend': trend
    }


def _fetch_dex_pairs():
    try:
        request_obj = Request(DEX_API_URL, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(request_obj) as resp:
            data = json.load(resp)
            return data.get('pairs', [])
    except (URLError, HTTPError, json.JSONDecodeError):
        return []



def _helius_rpc(method, params):
    if not HELIUS_RPC_URL:
        return None
    payload = {
        'jsonrpc': '2.0',
        'id': int(datetime.utcnow().timestamp() * 1000),
        'method': method,
        'params': params
    }
    try:
        request_obj = Request(HELIUS_RPC_URL, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
        with urlopen(request_obj, timeout=15) as resp:
            raw = resp.read().decode('utf-8')
            data = json.loads(raw)
            if isinstance(data, dict) and 'error' in data:
                return None
            return data.get('result') if isinstance(data, dict) else None
    except Exception:
        return None


def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _load_coinbase_bases() -> set[str]:
    if not os.path.exists(COINBASE_PRODUCTS_PATH):
        return set()
    try:
        products = json.load(open(COINBASE_PRODUCTS_PATH, 'r'))
    except Exception:
        return set()
    allowed_quotes = {'USD', 'USDC', 'USDT'}
    bases = set()
    for product in products:
        base = (product.get('base_currency') or '').upper()
        quote = (product.get('quote_currency') or '').upper()
        if not base or quote not in allowed_quotes:
            continue
        if product.get('cancel_only') or product.get('trading_disabled'):
            continue
        bases.add(base)
    return bases


def _ui_amount(entry):
    amount_info = entry.get('uiTokenAmount', {}) if isinstance(entry, dict) else {}
    ui_val = amount_info.get('uiAmount')
    if ui_val is not None:
        try:
            return float(ui_val)
        except (TypeError, ValueError):
            return 0.0
    raw_amount = amount_info.get('amount')
    decimals = amount_info.get('decimals', 0)
    if raw_amount is None:
        return 0.0
    try:
        return float(raw_amount) / (10 ** int(decimals or 0))
    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0


def _fetch_pair_transactions(pair_address, limit=10):
    if not pair_address:
        return []
    signatures = _helius_rpc('getSignaturesForAddress', [pair_address, {'limit': limit}]) or []
    transactions = []
    for entry in signatures:
        signature = entry.get('signature') if isinstance(entry, dict) else None
        if not signature:
            continue
        tx = _helius_rpc('getTransaction', [signature, {'encoding': 'jsonParsed', 'maxSupportedTransactionVersion': 0, 'commitment': 'confirmed'}])
        if tx:
            if entry.get('blockTime') and not tx.get('blockTime'):
                tx['blockTime'] = entry.get('blockTime')
            transactions.append(tx)
        if len(transactions) >= limit:
            break
    return transactions


def _evaluate_wallet_flows(transactions, mint_address, price_usd, liquidity_usd):
    if not transactions or not mint_address:
        return {}
    price = _safe_float(price_usd) or 0.0
    liquidity = _safe_float(liquidity_usd) or 0.0
    wallet_stats = {}
    block_times = []
    for tx in transactions:
        meta = tx.get('meta') if isinstance(tx, dict) else None
        if not meta:
            continue
        block_time = tx.get('blockTime')
        if block_time:
            block_times.append(block_time)
        pre_map = {}
        for bal in meta.get('preTokenBalances', []) or []:
            if bal.get('mint') != mint_address:
                continue
            pre_map[bal.get('accountIndex')] = _ui_amount(bal)
        for post in meta.get('postTokenBalances', []) or []:
            if post.get('mint') != mint_address:
                continue
            owner = post.get('owner')
            if not owner:
                continue
            account_index = post.get('accountIndex')
            post_amt = _ui_amount(post)
            pre_amt = pre_map.get(account_index, 0.0)
            delta = post_amt - pre_amt
            if delta <= 0:
                continue
            stat = wallet_stats.setdefault(owner, {'amount': 0.0, 'tx_count': 0, 'new_wallet': False, 'latest_ts': 0})
            stat['amount'] += delta
            stat['tx_count'] += 1
            stat['latest_ts'] = max(stat['latest_ts'], block_time or 0)
            if account_index not in pre_map:
                stat['new_wallet'] = True
    total_wallets = len(wallet_stats)
    total_inflow_tokens = sum(stat['amount'] for stat in wallet_stats.values())
    total_inflow_usd = total_inflow_tokens * price if price else 0.0
    new_wallet_ratio = (sum(1 for stat in wallet_stats.values() if stat['new_wallet']) / total_wallets) if total_wallets else 0.0
    repeat_wallets = sum(1 for stat in wallet_stats.values() if stat['tx_count'] > 1)
    large_buy_threshold = max(5000.0, liquidity * 0.02) if price else 0.0
    whale_contrib = 0.0
    large_buy_count = 0
    if wallet_stats:
        sorted_wallets = sorted(wallet_stats.values(), key=lambda s: s['amount'], reverse=True)
        top_contributors = sorted_wallets[:3]
        for stat in top_contributors:
            whale_contrib += stat['amount'] * price if price else 0.0
        for stat in wallet_stats.values():
            usd_amount = stat['amount'] * price if price else 0.0
            if usd_amount >= large_buy_threshold > 0:
                large_buy_count += 1
    accumulation_score = None
    if liquidity > 0 and total_inflow_usd > 0:
        accumulation_score = min(1.0, total_inflow_usd / max(liquidity * 0.05, 1.0))
    whale_activity_score = None
    if total_inflow_usd > 0 and whale_contrib > 0:
        whale_activity_score = min(1.0, whale_contrib / total_inflow_usd)
    wallet_signal_components = []
    if accumulation_score is not None:
        wallet_signal_components.append(accumulation_score)
    if whale_activity_score is not None:
        wallet_signal_components.append(whale_activity_score)
    if total_wallets:
        wallet_signal_components.append(min(1.0, new_wallet_ratio))
    wallet_signal_score = sum(wallet_signal_components) / len(wallet_signal_components) if wallet_signal_components else None
    intel_window = None
    if block_times:
        intel_window = (max(block_times) - min(block_times)) / 60 if max(block_times) != min(block_times) else 0
    return {
        'wallet_accumulation_score': None if accumulation_score is None else round(accumulation_score, 6),
        'whale_activity_score': None if whale_activity_score is None else round(whale_activity_score, 6),
        'new_wallet_ratio': None if not total_wallets else round(new_wallet_ratio, 6),
        'wallet_intel_samples': total_wallets,
        'wallet_large_buy_count': large_buy_count,
        'wallet_repeat_wallets': repeat_wallets,
        'wallet_signal_score': None if wallet_signal_score is None else round(wallet_signal_score, 6),
        'wallet_intel_window_minutes': intel_window
    }


def _apply_wallet_intel(candidate):
    mint = candidate.get('solana_mint_address')
    pair_address = candidate.get('pair_address')
    if not (HELIUS_RPC_URL and mint and pair_address):
        candidate.setdefault('wallet_accumulation_score', None)
        candidate.setdefault('whale_activity_score', None)
        candidate.setdefault('new_wallet_ratio', None)
        candidate.setdefault('wallet_signal_score', None)
        return candidate
    transactions = _fetch_pair_transactions(pair_address, limit=8)
    metrics = _evaluate_wallet_flows(transactions, mint, candidate.get('price_usd'), candidate.get('liquidity_usd')) if transactions else {}
    candidate.update({
        'wallet_accumulation_score': metrics.get('wallet_accumulation_score'),
        'whale_activity_score': metrics.get('whale_activity_score'),
        'new_wallet_ratio': metrics.get('new_wallet_ratio'),
        'wallet_intel_samples': metrics.get('wallet_intel_samples'),
        'wallet_large_buy_count': metrics.get('wallet_large_buy_count'),
        'wallet_repeat_wallets': metrics.get('wallet_repeat_wallets'),
        'wallet_signal_score': metrics.get('wallet_signal_score'),
        'wallet_intel_window_minutes': metrics.get('wallet_intel_window_minutes')
    })
    signal = candidate.get('wallet_signal_score')
    if signal is not None and candidate.get('score') is not None:
        candidate['score'] = round(candidate['score'] * 0.6 + signal * 0.4, 6)
    return candidate

def _hours_since(timestamp_ms):
    if not timestamp_ms:
        return None
    try:
        created = datetime.fromtimestamp(int(timestamp_ms) / 1000)
    except (TypeError, ValueError):
        return None
    delta = datetime.utcnow() - created
    return delta.total_seconds() / 3600.0


def _score_pairs(pairs):
    scored = []
    for pair in pairs:
        liquidity = float(pair.get('liquidity', {}).get('usd') or 0)
        volume = pair.get('volume', {})
        volume_h24 = float(volume.get('h24') or 0)
        volume_h6 = float(volume.get('h6') or 0)
        volume_h1 = float(volume.get('h1') or 0)
        price_change = float(pair.get('priceChange', {}).get('h24') or 0)
        age_hours = _hours_since(pair.get('pairCreatedAt'))
        if liquidity < 50000 or volume_h24 < 100000 or price_change <= 0:
            continue
        if age_hours is not None and age_hours >= 48:
            continue

        volume_spike = 0.0
        if volume_h6 > 0 and volume_h1 > 0:
            volume_spike = volume_h1 / max(volume_h6 / 6, 1)
        elif volume_h24 > 0:
            volume_spike = volume_h24 / 100000

        liquidity_growth = liquidity / 50000

        txns = pair.get('txns', {}).get('h24', {})
        buys = float(txns.get('buys') or 0)
        sells = float(txns.get('sells') or 0)
        total_txns = buys + sells
        buy_pressure = ((buys - sells) / total_txns) if total_txns else 0

        scored.append({
            'pair': pair,
            'liquidity': liquidity,
            'volume_24h': volume_h24,
            'age_hours': age_hours,
            'price_change_24h': price_change,
            'volume_spike': volume_spike,
            'liquidity_growth': liquidity_growth,
            'buy_pressure': buy_pressure
        })

    if not scored:
        return []

    max_volume_spike = max(item['volume_spike'] for item in scored) or 1
    max_liquidity_growth = max(item['liquidity_growth'] for item in scored) or 1
    max_buy_pressure = max((abs(item['buy_pressure']) for item in scored), default=0) or 1

    ranked = []
    for item in scored:
        buy_component = (item['buy_pressure'] / max_buy_pressure) if max_buy_pressure else 0
        score = (
            _normalize(item['volume_spike'], max_volume_spike) * 0.4 +
            _normalize(item['liquidity_growth'], max_liquidity_growth) * 0.3 +
            buy_component * 0.3
        )
        pair = item['pair']
        base_token = pair.get('baseToken', {})
        candidate = {
            'symbol': base_token.get('symbol') or base_token.get('address'),
            'pair_address': pair.get('pairAddress'),
            'solana_mint_address': base_token.get('address') if pair.get('chainId') == 'solana' else None,
            'dex_id': pair.get('dexId'),
            'price_usd': pair.get('priceUsd'),
            'liquidity_usd': item['liquidity'],
            'volume_24h': item['volume_24h'],
            'age_hours': item['age_hours'],
            'price_change_24h': item['price_change_24h'],
            'buy_pressure': round(item['buy_pressure'], 4),
            'score': round(score, 6)
        }
        candidate = _apply_wallet_intel(candidate)
        ranked.append(candidate)

    ranked.sort(key=lambda x: x['score'], reverse=True)
    return ranked


def _save_candidates(candidates):
    os.makedirs(os.path.dirname(CANDIDATE_PATH), exist_ok=True)
    with open(CANDIDATE_PATH, 'w') as handle:
        json.dump(candidates, handle, indent=2)


def _write_market_state(state: dict):
    os.makedirs(os.path.dirname(MARKET_STATE_PATH), exist_ok=True)
    with open(MARKET_STATE_PATH, 'w') as handle:
        json.dump(state, handle, indent=2)


def _evaluate_market_state(ranked_entries, summary, timestamp):
    total_signals = len(ranked_entries)
    top_slice = ranked_entries[:5]
    avg_top_score = sum(entry['score'] for entry in top_slice) / len(top_slice) if top_slice else 0.0
    high_quality = [entry for entry in ranked_entries if entry.get('momentum', 0) >= 8.0 and entry.get('volume', 0) >= 75_000_000]
    breadth_positive = sum(1 for entry in ranked_entries if (entry.get('volume_acceleration_ratio') or 0) > 0)
    breadth_threshold = max(2, total_signals // 2) if total_signals else 0
    mode = 'high_opportunity' if (
        total_signals >= 3 and
        avg_top_score >= 0.5 and
        len(high_quality) >= 2 and
        breadth_positive >= breadth_threshold
    ) else 'baseline'
    return {
        'mode': mode,
        'computed_at': timestamp,
        'metrics': {
            'avg_top_score': avg_top_score,
            'high_quality_signals': len(high_quality),
            'breadth_positive': breadth_positive,
            'total_signals': total_signals
        },
        'top_opportunities': summary.get('top_opportunities', [])
    }


def market_scanner(tokens, volume_data, momentum_data):
    now = datetime.now()
    timestamp = now.strftime(timestamp_format)
    os.makedirs(LOG_DIR, exist_ok=True)
    log_path = os.path.join(LOG_DIR, f"{now.strftime('%Y-%m-%d')}.jsonl")

    recent_runs = _load_recent_runs(log_path, RUN_LOOKBACK)
    history = _build_history(recent_runs)
    coinbase_bases = _load_coinbase_bases()

    candidates = []
    for token in tokens:
        token = (token or '').upper().strip()
        if not token:
            continue
        if coinbase_bases and token not in coinbase_bases:
            continue
        volume = float(volume_data.get(token, 0) or 0)
        momentum = float(momentum_data.get(token, 0) or 0)
        if volume > HIGH_VOLUME_LEVEL and momentum > HIGH_MOMENTUM_LEVEL:
            candidates.append({
                'token': token,
                'volume': volume,
                'momentum': momentum,
                'coinbase_actionable': token in coinbase_bases,
            })

    filtered_entries = []
    for candidate in candidates:
        token = candidate['token']
        prev_entries = history.get(token, [])
        prev_count = len(prev_entries)
        last_entry = prev_entries[-1] if prev_entries else {}
        prev_volume = float(last_entry.get('volume') or 0)
        prev_momentum = float(last_entry.get('momentum') or 0)

        if prev_entries:
            improved = (candidate['momentum'] > prev_momentum) or (candidate['volume'] > prev_volume)
            if not improved:
                continue  # repeated weak signal, drop it
            status = 'strengthening'
        else:
            status = 'new'

        persistence = min(prev_count + 1, RUN_LOOKBACK)
        recent_entries = prev_entries[-5:]
        recent_volumes = [float(e.get('volume') or 0) for e in recent_entries if e.get('volume')]
        avg_recent_volume = (sum(recent_volumes) / len(recent_volumes)) if recent_volumes else None
        liquidity_change_ratio = (candidate['volume'] / avg_recent_volume) if avg_recent_volume else None
        volume_accel_ratio = ((candidate['volume'] - prev_volume) / prev_volume) if prev_volume else None
        recent_momentums = [float(e.get('momentum') or 0) for e in recent_entries if e.get('momentum')]
        avg_recent_momentum = (sum(recent_momentums) / len(recent_momentums)) if recent_momentums else None
        buy_pressure_proxy = None
        if avg_recent_momentum and avg_recent_momentum != 0:
            buy_pressure_proxy = (candidate['momentum'] - avg_recent_momentum) / abs(avg_recent_momentum)

        liquidity_component = _scale_positive_ratio(liquidity_change_ratio)
        buy_component = _scale_signed_ratio(buy_pressure_proxy)
        volume_component = _scale_signed_ratio(volume_accel_ratio)
        liquidity_health = round((liquidity_component * 0.4) + (buy_component * 0.3) + (volume_component * 0.3), 6)

        alignment = _compute_alignment(candidate['momentum'], prev_entries, now)

        entry = {
            'timestamp': timestamp,
            'token': token,
            'volume': round(candidate['volume'], 6),
            'momentum': round(candidate['momentum'], 6),
            'status': status,
            'persistence': persistence,
            'coinbase_actionable': candidate.get('coinbase_actionable', False),
            'liquidity_change_ratio': None if liquidity_change_ratio is None else round(liquidity_change_ratio, 6),
            'volume_acceleration_ratio': None if volume_accel_ratio is None else round(volume_accel_ratio, 6),
            'buy_pressure_proxy': None if buy_pressure_proxy is None else round(buy_pressure_proxy, 6),
            'liquidity_health': liquidity_health,
            'momentum_5m': alignment['momentum_5m'],
            'momentum_15m': alignment['momentum_15m'],
            'momentum_60m': alignment['momentum_60m'],
            'momentum_alignment_score': alignment['alignment'],
            'momentum_trend': alignment['trend']
        }
        filtered_entries.append(entry)

    if not filtered_entries:
        summary = {
            'timestamp': timestamp,
            'top_opportunities': []
        }
        market_state = _evaluate_market_state([], summary, timestamp)
        _write_market_state(market_state)
        _save_candidates([])
        return ["SUMMARY:" + json.dumps(summary)]

    max_momentum = max(entry['momentum'] for entry in filtered_entries)
    max_volume = max(entry['volume'] for entry in filtered_entries)

    for entry in filtered_entries:
        persistence_score = entry['persistence'] / RUN_LOOKBACK
        momentum_score = _normalize(entry['momentum'], max_momentum)
        volume_score = _normalize(entry['volume'], max_volume)
        liquidity_score = entry.get('liquidity_health', 0.5)
        alignment_score = entry.get('momentum_alignment_score', 0.5)
        composite = (
            momentum_score * 0.25 +
            volume_score * 0.25 +
            persistence_score * 0.2 +
            liquidity_score * 0.15 +
            alignment_score * 0.15
        )

        trend = entry.get('momentum_trend') or 'steady'
        if trend == 'fading':
            composite -= 0.08
        elif trend == 'isolated spike':
            composite -= 0.12
        elif trend == 'accelerating':
            composite += 0.05

        if entry['persistence'] < MIN_PERSISTENCE_FOR_PRIORITY:
            composite -= 0.08
        if entry['volume'] < STRONG_VOLUME_FLOOR:
            composite -= 0.05

        entry['momentum_score'] = round(momentum_score, 6)
        entry['volume_score'] = round(volume_score, 6)
        entry['persistence_score'] = round(persistence_score, 6)
        entry['liquidity_score'] = round(liquidity_score, 6)
        entry['alignment_score'] = round(alignment_score, 6)
        entry['score'] = round(max(composite, 0), 6)

    ranked = [
        entry for entry in sorted(filtered_entries, key=lambda e: e['score'], reverse=True)
        if entry['score'] >= HIGH_CONVICTION_SCORE_FLOOR
        and entry['persistence'] >= MIN_PERSISTENCE_FOR_PRIORITY
        and entry['volume'] >= STRONG_VOLUME_FLOOR
        and entry.get('momentum_trend') not in {'isolated spike'}
    ]
    top_three = ranked[:3]
    summary = {
        'timestamp': timestamp,
        'top_opportunities': [
            {
                'token': item['token'],
                'score': item['score'],
                'momentum': item['momentum'],
                'volume': item['volume'],
                'persistence': item['persistence'],
                'status': item['status'],
                'trend': item.get('momentum_trend')
            }
            for item in top_three
        ]
    }

    market_state = _evaluate_market_state(ranked, summary, timestamp)
    _write_market_state(market_state)

    with open(log_path, 'a') as f:
        for entry in filtered_entries:
            f.write(json.dumps(entry) + '\n')

    dex_candidates = _score_pairs(_fetch_dex_pairs())
    if dex_candidates:
        _save_candidates(dex_candidates)
    else:
        _save_candidates([])

    log_lines = [json.dumps(entry) for entry in filtered_entries]
    result_lines = ["SUMMARY:" + json.dumps(summary)]

    if dex_candidates:
        dex_summary = {
            'timestamp': timestamp,
            'top_dex_candidates': dex_candidates[:5]
        }
        result_lines.append("DEX_SUMMARY:" + json.dumps(dex_summary))

    result_lines.extend(log_lines)
    return result_lines


def _load_runtime_snapshot():
    try:
        from autonomous_market_loop import _fetch_market_snapshot, _prepare_scanner_payload
    except Exception:
        return [], {}, {}

    data = _fetch_market_snapshot()
    return _prepare_scanner_payload(data)


def main():
    tokens, volume_data, momentum_data = _load_runtime_snapshot()
    results = market_scanner(tokens, volume_data, momentum_data)
    for line in results:
        print(line)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
