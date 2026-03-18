import json
from datetime import datetime, timezone
from pathlib import Path

CACHE_DIR = Path('/data/.openclaw/workspace/cache')
CACHE_DIR.mkdir(parents=True, exist_ok=True)
API_USAGE_PATH = CACHE_DIR / 'api_usage.json'

def log_api_call(provider: str):
    provider = provider.lower().strip()
    if not provider:
        return
    now = datetime.now(timezone.utc)
    day = now.strftime('%Y-%m-%d')
    data = {}
    if API_USAGE_PATH.exists():
        try:
            data = json.loads(API_USAGE_PATH.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            data = {}
    entry = data.get(provider, {})
    if entry.get('day') != day:
        entry = {'day': day, 'count': 0}
    entry['count'] = entry.get('count', 0) + 1
    entry['updated_at'] = now.strftime('%Y-%m-%dT%H:%M:%SZ')
    data[provider] = entry
    API_USAGE_PATH.write_text(json.dumps(data, indent=2), encoding='utf-8')
