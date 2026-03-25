import argparse
import json
import os
import sys
from datetime import datetime, timezone
from importlib.machinery import SourceFileLoader
from pathlib import Path
from typing import Dict, List
from urllib.request import urlopen, URLError, Request

from api_usage import log_api_call
from dashboard.modes import get_modes

WORKSPACE = "/home/lokiai/.openclaw/workspace"
SYSTEM_LOG_DIR = os.path.join(WORKSPACE, "system_logs")
LOG_FILE = os.path.join(SYSTEM_LOG_DIR, "autonomous_market_loop.log")
SECRET_ENV_FILE = os.path.join(WORKSPACE, "secrets", "x_api_credentials.env")
COINGECKO_URL = (
    "https://api.coingecko.com/api/v3/coins/markets"
    "?vs_currency=usd&order=volume_desc&per_page=100&page=1&price_change_percentage=1h,24h"
)
BINANCE_TICKER_URL = "https://api.binance.com/api/v3/ticker/24hr"
BINANCE_QUOTES = ("USDT", "FDUSD", "BUSD", "USDC", "TUSD")
OKX_TICKER_URL = "https://www.okx.com/api/v5/market/tickers?instType=SPOT"
OKX_QUOTES = ("USDT", "USDC", "USD", "FDUSD")
COINBASE_PRODUCTS_URL = "https://api.exchange.coinbase.com/products"
COINBASE_STATS_URL = "https://api.exchange.coinbase.com/products/stats"
COINBASE_QUOTES = ("USD", "USDC", "USDT")
COINPAPRIKA_TICKER_URL = "https://api.coinpaprika.com/v1/tickers"

CACHE_DIR = Path(os.path.join(WORKSPACE, 'cache'))
CACHE_DIR.mkdir(parents=True, exist_ok=True)
COINGECKO_CACHE_PATH = CACHE_DIR / 'coingecko_snapshot.json'
COINGECKO_CACHE_TTL = 300

SKILL_PATHS = {
    'market_scanner': os.path.join(WORKSPACE, 'skills', 'market_scanner', 'market_scanner.py'),
    'paper_trader': os.path.join(WORKSPACE, 'skills', 'paper-trader', 'paper_trader_v2.py'),
    'market_broadcaster': os.path.join(WORKSPACE, 'skills', 'market-broadcaster', 'market_broadcaster.py'),
    'performance_analyzer': os.path.join(WORKSPACE, 'skills', 'performance-analyzer', 'performance_analyzer.py'),
    'position_manager': os.path.join(WORKSPACE, 'skills', 'position-manager', 'position_manager.py'),
    'sol_paper_trader': os.path.join(WORKSPACE, 'skills', 'sol-paper-trader', 'sol_paper_trader.py'),
    'telegram_sender': os.path.join(WORKSPACE, 'skills', 'telegram_sender', 'telegram_sender.py'),
    'x_autoposter': os.path.join(WORKSPACE, 'skills', 'x-autoposter', 'x_autoposter.py'),
}


def _load_secret_env():
    if not os.path.exists(SECRET_ENV_FILE):
        return
    with open(SECRET_ENV_FILE, 'r') as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('export '):
                line = line.split('export ', 1)[1]
            if '=' not in line:
                continue
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                os.environ[key] = value


_load_secret_env()


def _ensure_log_dir():
    os.makedirs(SYSTEM_LOG_DIR, exist_ok=True)


def _append_log(entry: Dict):
    _ensure_log_dir()
    with open(LOG_FILE, 'a') as handle:
        handle.write(json.dumps(entry) + "\n")


def _load_module(task: str):
    path = SKILL_PATHS[task]
    return SourceFileLoader(task, path).load_module()


def lint_skills() -> bool:
    failures: List[str] = []
    entrypoint_aliases = {
        'paper_trader': ('paper_trader_v2', 'paper_trader'),
    }
    for task, path in SKILL_PATHS.items():
        try:
            module = _load_module(task)
        except FileNotFoundError:
            failures.append(f"{task}: file not found ({path})")
            continue
        expected = entrypoint_aliases.get(task, (task,))
        if not any(hasattr(module, name) for name in expected):
            pretty = ' or '.join(f"'{name}()'" for name in expected)
            failures.append(f"{task}: missing {pretty} entrypoint")
    if failures:
        print("Skill lint failures:")
        for failure in failures:
            print(f" - {failure}")
        return False
    print(f"Skill lint passed for {len(SKILL_PATHS)} task(s).")
    return True


def _write_coingecko_cache(data):
    payload = {
        'fetched_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'data': data
    }
    with open(COINGECKO_CACHE_PATH, 'w') as handle:
        json.dump(payload, handle)


def _fetch_market_snapshot():
    with urlopen(COINGECKO_URL) as resp:
        data = json.load(resp)
    log_api_call('coingecko')
    _write_coingecko_cache(data)
    return data


def _fetch_binance_metrics():
    try:
        request_obj = Request(BINANCE_TICKER_URL, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(request_obj) as resp:
            payload = json.load(resp)
    except (URLError, json.JSONDecodeError):
        return {}
    metrics = {}
    for item in payload:
        symbol = (item.get('symbol') or '').upper()
        base = None
        for quote in BINANCE_QUOTES:
            if symbol.endswith(quote):
                base = symbol[:-len(quote)]
                break
        if not base or not base.isalpha():
            continue
        try:
            quote_volume = float(item.get('quoteVolume') or 0.0)
            price_change_pct = float(item.get('priceChangePercent') or 0.0)
        except (TypeError, ValueError):
            continue
        if quote_volume <= 0:
            continue
        metrics[base] = {
            'volume': quote_volume,
            'momentum': price_change_pct
        }
    return metrics


def _fetch_okx_metrics():
    try:
        request_obj = Request(OKX_TICKER_URL, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(request_obj) as resp:
            payload = json.load(resp)
    except (URLError, json.JSONDecodeError):
        return {}
    if str(payload.get('code')) != '0':
        return {}
    metrics = {}
    for item in payload.get('data', []):
        inst_id = item.get('instId') or ''
        if '-' not in inst_id:
            continue
        base, quote = inst_id.split('-', 1)
        if quote not in OKX_QUOTES:
            continue
        try:
            volume = float(item.get('volCcy24h') or 0.0)
            last_price = float(item.get('last') or 0.0)
            open_price = float(item.get('open24h') or 0.0)
        except (TypeError, ValueError):
            continue
        if volume <= 0 or open_price <= 0:
            continue
        momentum = ((last_price - open_price) / open_price) * 100.0
        metrics[base.upper()] = {
            'volume': volume,
            'momentum': momentum
        }
    return metrics


def _fetch_coinbase_metrics():
    try:
        products_req = Request(COINBASE_PRODUCTS_URL, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(products_req) as resp:
            products = json.load(resp)
    except (URLError, json.JSONDecodeError):
        return {}
    product_map = {}
    for product in products:
        product_id = product.get('id')
        base = product.get('base_currency')
        quote = product.get('quote_currency')
        if not product_id or not base or not quote:
            continue
        product_map[product_id] = {'base': base.upper(), 'quote': quote.upper()}
    try:
        stats_req = Request(COINBASE_STATS_URL, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(stats_req) as resp:
            stats_payload = json.load(resp)
    except (URLError, json.JSONDecodeError):
        return {}
    metrics = {}
    for product_id, stat_entry in stats_payload.items():
        mapping = product_map.get(product_id)
        if not mapping or mapping['quote'] not in COINBASE_QUOTES:
            continue
        stats_24h = stat_entry.get('stats_24hour') or {}
        try:
            open_price = float(stats_24h.get('open') or 0.0)
            last_price = float(stats_24h.get('last') or 0.0)
            base_volume = float(stats_24h.get('volume') or 0.0)
        except (TypeError, ValueError):
            continue
        if open_price <= 0 or last_price <= 0 or base_volume <= 0:
            continue
        quote_volume = base_volume * last_price
        momentum = ((last_price - open_price) / open_price) * 100.0
        metrics[mapping['base']] = {
            'volume': quote_volume,
            'momentum': momentum
        }
    return metrics


def _fetch_coinpaprika_metrics():
    try:
        request_obj = Request(COINPAPRIKA_TICKER_URL, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(request_obj) as resp:
            payload = json.load(resp)
    except (URLError, json.JSONDecodeError):
        return {}
    metrics = {}
    for item in payload:
        symbol = (item.get('symbol') or '').upper()
        if not symbol:
            continue
        usd = (item.get('quotes') or {}).get('USD') or {}
        try:
            volume = float(usd.get('volume_24h') or 0.0)
            momentum = float(usd.get('percent_change_24h') or 0.0)
        except (TypeError, ValueError):
            continue
        if volume <= 0:
            continue
        metrics[symbol] = {'volume': volume, 'momentum': momentum}
    return metrics


def _prepare_scanner_payload(data: List[Dict]):
    tokens = []
    volume_data = {}
    momentum_data = {}
    for coin in data:
        symbol = (coin.get('symbol') or '').upper()
        if not symbol:
            continue
        if symbol not in volume_data:
            tokens.append(symbol)
        volume_data[symbol] = coin.get('total_volume') or 0
        momentum_data[symbol] = coin.get('price_change_percentage_24h') or 0

    binance_metrics = _fetch_binance_metrics()
    for symbol, stats in binance_metrics.items():
        if symbol not in volume_data:
            tokens.append(symbol)
        existing_volume = float(volume_data.get(symbol, 0) or 0)
        if stats['volume'] > existing_volume:
            volume_data[symbol] = stats['volume']
        momentum_data.setdefault(symbol, stats['momentum'])

    okx_metrics = _fetch_okx_metrics()
    for symbol, stats in okx_metrics.items():
        if symbol not in volume_data:
            tokens.append(symbol)
        existing_volume = float(volume_data.get(symbol, 0) or 0)
        if stats['volume'] > existing_volume:
            volume_data[symbol] = stats['volume']
        momentum_data.setdefault(symbol, stats['momentum'])

    coinbase_metrics = _fetch_coinbase_metrics()
    for symbol, stats in coinbase_metrics.items():
        if symbol not in volume_data:
            tokens.append(symbol)
        existing_volume = float(volume_data.get(symbol, 0) or 0)
        if stats['volume'] > existing_volume:
            volume_data[symbol] = stats['volume']
        momentum_data.setdefault(symbol, stats['momentum'])

    coinpaprika_metrics = _fetch_coinpaprika_metrics()
    for symbol, stats in coinpaprika_metrics.items():
        if symbol not in volume_data:
            tokens.append(symbol)
        existing_volume = float(volume_data.get(symbol, 0) or 0)
        if stats['volume'] > existing_volume:
            volume_data[symbol] = stats['volume']
        momentum_data.setdefault(symbol, stats['momentum'])

    return tokens, volume_data, momentum_data


def run_market_scanner():
    data = _fetch_market_snapshot()
    tokens, volume_data, momentum_data = _prepare_scanner_payload(data)
    module = _load_module('market_scanner')
    results = module.market_scanner(tokens, volume_data, momentum_data)

    summary = None
    if results:
        first = results[0]
        if isinstance(first, str) and first.startswith('SUMMARY:'):
            try:
                summary = json.loads(first.replace('SUMMARY:', '', 1))
            except json.JSONDecodeError:
                summary = {'error': 'Failed to parse summary'}

    signals = len(results) - 1 if summary else len(results)
    top_lines = []
    if summary and summary.get('top_opportunities'):
        for item in summary['top_opportunities'][:3]:
            token = item.get('token', '?')
            momentum = item.get('momentum', 0.0)
            volume = item.get('volume', 0.0)
            trend = item.get('trend') or item.get('status', 'steady')
            top_lines.append(f"• {token}: {momentum:+.1f}% | ${volume:,.0f} vol | {trend}")
    header = f"📊 Scanner {summary.get('timestamp') if summary else ''}: {signals} signals"
    message = "\n".join([header] + top_lines) if top_lines else header
    details = {'signals': signals, 'summary': summary}
    return message.strip(), details


def run_paper_trader():
    module = _load_module('paper_trader')
    runner = getattr(module, 'paper_trader_v2', None) or getattr(module, 'paper_trader', None)
    if runner is None:
        raise AttributeError('paper_trader module missing paper_trader_v2()/paper_trader() entrypoint')
    result = runner()
    summary = result.get('summary') if isinstance(result, dict) else None
    open_positions = result.get('open_positions', []) if isinstance(result, dict) else []
    message = summary or f"Paper trader updated ({len(open_positions)} open)."
    details = {'summary': summary, 'open_positions': len(open_positions)}
    return message, details


def run_market_broadcaster():
    module = _load_module('market_broadcaster')
    result = module.market_broadcaster()
    message = f"Market broadcaster post ready ({result.get('post_path')})."
    details = {
        'post_path': result.get('post_path'),
        'thread_path': result.get('thread_path'),
        'top_tokens': [entry.get('token') for entry in result.get('top_ranked', [])]
    }
    return message, details


def run_telegram_sender():
    module = _load_module('telegram_sender')
    result = module.telegram_sender()
    cycle = result.get('cycle_count')
    message = f"Telegram status pushed (cycle {cycle})."
    details = result
    return message, details


def run_x_autoposter():
    module = _load_module('x_autoposter')
    result = module.x_autoposter()
    message = result.get('message') or 'X autoposter run completed.'
    if result.get('tweet_id'):
        message += f" Tweet ID: {result['tweet_id']}"
    details = result
    return message, details


def run_performance_analyzer():
    module = _load_module('performance_analyzer')
    result = module.performance_analyzer()
    message = f"Performance report refreshed ({result.get('report_path')})."
    details = {
        'report_path': result.get('report_path'),
        'total_trades': result.get('metrics', {}).get('total_trades', 0)
    }
    return message, details


def run_position_manager():
    module = _load_module('position_manager')
    result = module.position_manager()
    message = f"Position manager actions: {len(result)} trade(s) evaluated."
    details = {'actions': result}
    closed = [action for action in result if action.get('action') == 'CLOSE']
    if closed:
        reload_message, reload_details = run_paper_trader()
        message += f" Triggered {len(closed)} new trade cycle(s)."
        details['paper_trader_reload'] = reload_details
    return message, details


def run_sol_paper_trader():
    module = _load_module('sol_paper_trader')
    result = module.sol_paper_trader()
    open_count = len(result.get('open_positions', []))
    closed_count = len(result.get('closed_trades', []))
    message = f"Sol paper trader open positions: {open_count}; closed this run: {closed_count}."
    details = {
        'summary': result.get('summary'),
        'open_positions_path': result.get('open_positions_path'),
        'trades_log_path': result.get('trades_log_path')
    }
    return message, details


def main(task: str):
    now_iso = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    status = 'ok'
    message = ''
    details = {}
    modes = get_modes()
    task_mode_map = {
        'market_broadcaster': 'market_broadcaster',
        'telegram_sender': 'telegram_sender',
        'x_autoposter': 'x_autoposter',
        'performance_analyzer': 'performance_analyzer',
    }
    if task in task_mode_map and not modes.get(task_mode_map[task], True):
        status = 'skipped'
        message = f"{task} skipped (disabled in dashboard modes)."
        details = {'reason': 'dashboard_mode_disabled', 'component': task_mode_map[task]}
    else:
        try:
            if task == 'market_scanner':
                message, details = run_market_scanner()
            elif task == 'paper_trader':
                message, details = run_paper_trader()
            elif task == 'market_broadcaster':
                message, details = run_market_broadcaster()
            elif task == 'telegram_sender':
                message, details = run_telegram_sender()
            elif task == 'x_autoposter':
                message, details = run_x_autoposter()
            elif task == 'performance_analyzer':
                message, details = run_performance_analyzer()
            elif task == 'position_manager':
                message, details = run_position_manager()
            elif task == 'sol_paper_trader':
                message, details = run_sol_paper_trader()
            else:
                raise ValueError(f"Unknown task: {task}")
        except (URLError, ConnectionError) as net_err:
            status = 'network_error'
            message = str(net_err)
        except Exception as exc:  # pylint: disable=broad-except
            status = 'error'
            message = str(exc)

    log_entry = {
        'timestamp': now_iso,
        'task': task,
        'status': status,
        'message': message,
        'details': details,
    }
    _append_log(log_entry)
    if message:
        print(message)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Autonomous Market Loop runner')
    parser.add_argument('--task', choices=[
        'market_scanner', 'paper_trader', 'market_broadcaster', 'telegram_sender', 'x_autoposter', 'performance_analyzer', 'position_manager', 'sol_paper_trader'
    ], help='Specific task to execute once')
    parser.add_argument('--lint', action='store_true', help='Verify that every skill exposes the required entrypoint and exit')
    args = parser.parse_args()

    if args.lint:
        ok = lint_skills()
        sys.exit(0 if ok else 1)

    if not args.task:
        parser.error('Either --task or --lint must be provided.')

    main(args.task)
