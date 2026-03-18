import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from api_usage import log_api_call

WORKSPACE = "/data/.openclaw/workspace"
DATA_DIR = os.path.join(WORKSPACE, "sol_paper_trades")
OPEN_POSITIONS_PATH = os.path.join(DATA_DIR, "open_positions.json")
TRADES_LOG_PATH = os.path.join(DATA_DIR, "trades_log.json")
CONFIG_PATH = os.path.join(WORKSPACE, "secrets", "birdeye_api_credentials.env")

API_BASE = "https://public-api.birdeye.so"
TOKEN_LIST_PATH = "/defi/v3/token/list"
TOKEN_OVERVIEW_PATH = "/defi/token_overview"

POSITION_SIZE_USD = 3.0
TAKE_PROFIT_PCT = 8.0
STOP_LOSS_PCT = -4.0
TIME_STOP_HOURS = 3.5
MAX_OPEN_POSITIONS = 10
MIN_LIQUIDITY_USD = 30000.0
MIN_VOLUME_USD = 150000.0
FETCH_LIMIT = 300
PAGE_SIZE = 100
PARTIAL_FIRST_PCT = 4.0
PARTIAL_PORTION = 0.5
TRAIL_GAP_PCT = 3.0

BLOCKLIST_SYMBOLS = {
    "SOL", "WSOL", "MSOL", "STSOL", "JSOL", "JSOS", "JITOSOL", "JIT", "BNSOL",
    "PSOL", "BSOL", "MSO", "bbSOL", "dzSOL", "dSOL", "sctmSOL", "fwdSOL",
    "USDC", "USDT", "USDH", "USDS", "USDL", "USDR", "TUSD", "USDP", "DAI",
}
BLOCKLIST_KEYWORDS = {"STAKED", "STAKING", "WRAPPED"}
FOCUS_SYMBOLS = {
    "WIF", "BONK", "BOME", "WEN", "MYRO", "POPCAT", "PENGU", "GME", "ENA",
    "DOGS", "TRUMP", "PUMP", "FARTCOIN", "HYPE", "JLP"
}

CACHE = {}


def _load_api_key() -> str:
    key = os.environ.get("BIRDEYE_API_KEY")
    if key:
        return key.strip()
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.upper().startswith("BIRDEYE_API_KEY"):
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        return parts[1].strip()
    raise RuntimeError("BIRDEYE_API_KEY not found in environment or secrets file")


def _request_json(path: str, params: Dict[str, str]) -> Dict:
    api_key = _load_api_key()
    query = urlencode(params)
    url = f"{API_BASE}{path}?{query}" if query else f"{API_BASE}{path}"
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (compatible; LokiAI/1.0)",
        "X-API-KEY": api_key,
        "x-chain": "solana",
    }
    req = Request(url, headers=headers)
    with urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _load_json(path: str, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as handle:
            try:
                return json.load(handle)
            except json.JSONDecodeError:
                return default
    return default


def _save_json(path: str, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)


def _append_trade_event(entry: Dict):
    history = _load_json(TRADES_LOG_PATH, [])
    history.append(entry)
    _save_json(TRADES_LOG_PATH, history)


def _hours_open(entry_time: str) -> float:
    if not entry_time:
        return 0.0
    try:
        start = datetime.fromisoformat(entry_time.replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    delta = datetime.now(timezone.utc) - start
    return delta.total_seconds() / 3600.0


def _fetch_token_pages(limit: int) -> List[Dict]:
    items: List[Dict] = []
    offset = 0
    while len(items) < limit:
        batch_size = min(PAGE_SIZE, limit - len(items))
        try:
            resp = _request_json(
                TOKEN_LIST_PATH,
                {"chain": "solana", "offset": offset, "limit": batch_size}
            )
        except (HTTPError, URLError, RuntimeError):
            break
        data = (resp or {}).get("data", {})
        batch = data.get("items", [])
        if not batch:
            break
        items.extend(batch)
        offset += batch_size
        if not data.get("has_next"):
            break
    return items


def _should_skip(symbol: str, name: str) -> bool:
    up_symbol = (symbol or "").upper()
    up_name = (name or "").upper()
    if up_symbol in BLOCKLIST_SYMBOLS:
        return True
    if any(keyword in up_name for keyword in BLOCKLIST_KEYWORDS):
        return True
    if "USD" in up_symbol:
        return True
    if up_symbol.endswith("SOL"):
        return True
    return False


def _filter_candidates(items: List[Dict]) -> Tuple[List[Dict], Dict[str, Dict]]:
    filtered: List[Dict] = []
    token_map: Dict[str, Dict] = {}
    for item in items:
        address = item.get("address")
        symbol = item.get("symbol") or ""
        name = item.get("name") or ""
        if not address or address in token_map:
            continue
        price = float(item.get("price") or 0)
        volume = float(item.get("volume_24h_usd") or 0)
        liquidity = float(item.get("liquidity") or 0)
        if price <= 0:
            continue
        if liquidity < MIN_LIQUIDITY_USD or volume < MIN_VOLUME_USD:
            continue
        if _should_skip(symbol, name):
            continue
        enriched = {
            "address": address,
            "symbol": symbol.upper(),
            "name": name,
            "price": price,
            "volume_24h_usd": volume,
            "liquidity_usd": liquidity,
            "market_cap": item.get("market_cap"),
        }
        filtered.append(enriched)
        token_map[address] = enriched
    filtered.sort(key=lambda entry: entry.get("volume_24h_usd", 0), reverse=True)
    focus_bucket = [entry for entry in filtered if entry.get("symbol") in FOCUS_SYMBOLS]
    other_bucket = [entry for entry in filtered if entry.get("symbol") not in FOCUS_SYMBOLS]
    return focus_bucket + other_bucket, token_map


def _fetch_token_overview(address: str) -> Dict:
    if address in CACHE:
        return CACHE[address]
    try:
        resp = _request_json(TOKEN_OVERVIEW_PATH, {"address": address, "chain": "solana"})
        data = (resp or {}).get("data") or resp.get("token") or resp
    except (HTTPError, URLError, RuntimeError, AttributeError):
        data = None
    if isinstance(data, dict):
        CACHE[address] = data
    return data or {}


def _get_price_for_position(position: Dict, token_map: Dict[str, Dict]) -> float:
    address = position.get("address")
    if address in token_map:
        return float(token_map[address].get("price") or 0)
    overview = _fetch_token_overview(address)
    try:
        return float(overview.get("price") or overview.get("current_price") or 0)
    except (TypeError, ValueError):
        return 0.0


def _close_position(position: Dict, price: float, reason: str, category: str) -> Dict:
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    record = position.copy()
    record.update({
        "status": "closed",
        "exit_price": price,
        "exit_time": now_iso,
        "exit_reason": reason,
        "exit_category": category,
        "pnl_percent": round(position.get("pnl_percent", 0.0), 4),
    })
    return record


def sol_paper_trader():
    os.makedirs(DATA_DIR, exist_ok=True)
    candidates_raw = _fetch_token_pages(FETCH_LIMIT)
    candidates, token_map = _filter_candidates(candidates_raw)

    open_positions = _load_json(OPEN_POSITIONS_PATH, [])
    closed_this_run: List[Dict] = []
    updated_positions: List[Dict] = []
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for position in open_positions:
        current_price = _get_price_for_position(position, token_map)
        entry_price = float(position.get("entry_price") or 0)
        if current_price <= 0 or entry_price <= 0:
            updated_positions.append(position)
            continue
        pnl_pct = ((current_price - entry_price) / entry_price) * 100.0
        position["current_price"] = current_price
        position["pnl_percent"] = round(pnl_pct, 4)
        position["last_updated"] = now_iso

        target_price = float(position.get("target_price") or entry_price)
        stop_price = float(position.get("stop_price") or entry_price)
        hours_open = _hours_open(position.get("entry_time"))
        exit_reason = None
        exit_category = None

        if position.get("trail_active"):
            trail_high = max(float(position.get("trail_high") or current_price), current_price)
            position["trail_high"] = trail_high
            trail_stop = trail_high * (1 - TRAIL_GAP_PCT / 100)
            if trail_stop > stop_price:
                stop_price = trail_stop
        position["stop_price"] = round(stop_price, 6)

        if current_price >= target_price:
            exit_reason = "take_profit"
            exit_category = "TP"
        elif current_price <= stop_price:
            exit_reason = "stop_loss"
            exit_category = "SL"
        elif hours_open >= TIME_STOP_HOURS and abs(pnl_pct) < 1.0:
            exit_reason = f"time_stop_{int(TIME_STOP_HOURS)}h"
            exit_category = "TIME"

        if exit_reason:
            closed = _close_position(position, current_price, exit_reason, exit_category)
            closed_this_run.append(closed)
        else:
            if not position.get("partial_50_hit") and pnl_pct >= PARTIAL_FIRST_PCT:
                size_usd = float(position.get("position_size_usd") or 0)
                if size_usd > 0:
                    realized_usd = size_usd * PARTIAL_PORTION * (pnl_pct / 100)
                    remaining_size = size_usd * (1 - PARTIAL_PORTION)
                    position["position_size_usd"] = round(remaining_size, 2)
                    position["partial_50_hit"] = True
                    position["trail_active"] = True
                    position["trail_high"] = current_price
                    position["stop_price"] = round(entry_price, 6)
                    _append_trade_event({
                        "token": position.get("token"),
                        "address": position.get("address"),
                        "status": "partial_close",
                        "portion_closed": PARTIAL_PORTION,
                        "exit_time": now_iso,
                        "exit_price": current_price,
                        "pnl_percent": round(pnl_pct, 4),
                        "realized_usd": round(realized_usd, 4)
                    })
            updated_positions.append(position)

    open_addresses = {pos.get("address") for pos in updated_positions}
    for entry in candidates:
        if len(updated_positions) >= MAX_OPEN_POSITIONS:
            break
        address = entry.get("address")
        if not address or address in open_addresses:
            continue
        price = entry.get("price")
        if price is None or price <= 0:
            continue
        entry_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        target_price = price * (1 + TAKE_PROFIT_PCT / 100)
        stop_price = price * (1 + STOP_LOSS_PCT / 100)
        position = {
            "token": entry.get("symbol"),
            "name": entry.get("name"),
            "address": address,
            "entry_time": entry_time,
            "entry_price": price,
            "position_size_usd": POSITION_SIZE_USD,
            "target_price": round(target_price, 6),
            "stop_price": round(stop_price, 6),
            "status": "open",
            "current_price": price,
            "pnl_percent": 0.0,
            "last_updated": entry_time,
            "volume_24h_usd": entry.get("volume_24h_usd"),
            "liquidity_usd": entry.get("liquidity_usd"),
            "partial_50_hit": False,
            "trail_active": False,
            "trail_high": price,
        }
        updated_positions.append(position)
        open_addresses.add(address)

    _save_json(OPEN_POSITIONS_PATH, updated_positions)
    if closed_this_run:
        history = _load_json(TRADES_LOG_PATH, [])
        history.extend(closed_this_run)
        _save_json(TRADES_LOG_PATH, history)
    elif not os.path.exists(TRADES_LOG_PATH):
        _save_json(TRADES_LOG_PATH, [])

    open_summary = [
        f"{pos.get('token')} {pos.get('pnl_percent', 0.0):+.2f}% (entry {pos.get('entry_price'):.4g})"
        for pos in updated_positions
    ]
    closed_summary = [
        f"{trade.get('token')} {trade.get('pnl_percent', 0.0):+.2f}% ({trade.get('exit_category')})"
        for trade in closed_this_run
    ] or ["None"]

    summary_lines = [
        "Solana paper trading update",
        "",
        "Open positions:",
        "\n".join(open_summary) if open_summary else "None",
        "",
        "Closed this run:",
        "\n".join(closed_summary),
    ]
    summary = "\n".join(summary_lines)

    return {
        "timestamp": now_iso,
        "open_positions": updated_positions,
        "closed_trades": closed_this_run,
        "summary": summary,
        "candidates_considered": candidates[:10],
        "open_positions_path": OPEN_POSITIONS_PATH,
        "trades_log_path": TRADES_LOG_PATH,
    }


if __name__ == "__main__":
    result = sol_paper_trader()
    print(json.dumps(result, indent=2))
