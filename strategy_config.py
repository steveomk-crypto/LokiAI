import json
import os
import threading

CONFIG_PATH = "/data/.openclaw/workspace/strategy/strategy_config.json"
DEFAULTS = {
    "momentum_threshold": 3.0,
    "persistence_requirement": 1,
    "time_stop_hours": 2.0,
    "stop_loss_pct": -4.0,
    "last_optimized_trade_count": 0,
}
_lock = threading.Lock()
_cache = None


def _load_config():
    global _cache
    if _cache is not None:
        return _cache
    with _lock:
        if _cache is not None:
            return _cache
        if not os.path.exists(CONFIG_PATH):
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            with open(CONFIG_PATH, "w", encoding="utf-8") as handle:
                json.dump(DEFAULTS, handle, indent=2)
        with open(CONFIG_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        merged = DEFAULTS.copy()
        merged.update(data or {})
        _cache = merged
        return merged


def get_strategy_value(key: str):
    return _load_config().get(key, DEFAULTS.get(key))


def refresh_cache():
    global _cache
    with _lock:
        _cache = None
        return _load_config()
