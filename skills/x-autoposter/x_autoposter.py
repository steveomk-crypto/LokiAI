import json
import os
import sys
import time
import hmac
import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional
from urllib import parse, request, error

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from ops_state import load_ops_state

POSTS_DIR = Path("/data/.openclaw/workspace/x_posts")
POST_LOG = POSTS_DIR / "post_log.json"
QUEUE_DEFAULT_DIR = Path("/data/.openclaw/workspace/queues/market_radar")
CHANNEL_NAME = "x_autoposter"
API_URL = "https://api.x.com/2/tweets"
SECRET_ENV_FILE = Path("/data/.openclaw/workspace/secrets/x_api_credentials.env")

MAX_POSTS_PER_DAY = 3
MIN_POST_SPACING_HOURS = 2
STRONG_MIN_VOLUME = 25_000_000  # USD
STRONG_MIN_MOMENTUM = 8.0


def _load_secret_env():
    if not SECRET_ENV_FILE.exists():
        return
    for line in SECRET_ENV_FILE.read_text(encoding='utf-8').splitlines():
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
        if key and key not in os.environ:
            os.environ[key] = value


_load_secret_env()


def _percent_encode(value: str) -> str:
    return parse.quote(str(value), safe='~-._')


def _generate_nonce(length: int = 32) -> str:
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def _load_env_var(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Environment variable {name} is not set")
    return value


def _latest_post_file() -> Path:
    if not POSTS_DIR.exists():
        raise FileNotFoundError(f"Post directory not found: {POSTS_DIR}")
    post_files = [f for f in POSTS_DIR.glob("post_*.txt") if f.is_file()]
    if not post_files:
        raise FileNotFoundError("No post_*.txt files found in x_posts directory")
    return max(post_files, key=lambda p: p.stat().st_mtime)


def _read_post_text(path: Path) -> str:
    text = path.read_text(encoding='utf-8').strip()
    if not text:
        raise ValueError(f"Post file {path} is empty")
    return text


def _build_oauth_header(method: str, url: str, consumer_key: str, consumer_secret: str,
                         token: str, token_secret: str) -> str:
    timestamp = str(int(time.time()))
    nonce = _generate_nonce()
    oauth_params = {
        'oauth_consumer_key': consumer_key,
        'oauth_nonce': nonce,
        'oauth_signature_method': 'HMAC-SHA1',
        'oauth_timestamp': timestamp,
        'oauth_token': token,
        'oauth_version': '1.0'
    }

    parameter_string = '&'.join(
        f"{_percent_encode(k)}={_percent_encode(v)}" for k, v in sorted(oauth_params.items())
    )
    base_elems = [method.upper(), _percent_encode(url), _percent_encode(parameter_string)]
    base_string = '&'.join(base_elems)
    signing_key = '&'.join([_percent_encode(consumer_secret), _percent_encode(token_secret)])
    digest = hmac.new(signing_key.encode('utf-8'), base_string.encode('utf-8'), hashlib.sha1).digest()
    signature = base64.b64encode(digest).decode('utf-8')
    oauth_params['oauth_signature'] = signature

    header = 'OAuth ' + ', '.join(
        f"{_percent_encode(k)}=\"{_percent_encode(v)}\"" for k, v in oauth_params.items()
    )
    return header


def _send_tweet(text: str) -> Dict:
    consumer_key = _load_env_var('X_API_KEY')
    consumer_secret = _load_env_var('X_API_SECRET')
    access_token = _load_env_var('X_ACCESS_TOKEN')
    access_secret = _load_env_var('X_ACCESS_SECRET')

    body = json.dumps({'text': text}).encode('utf-8')
    headers = {
        'Content-Type': 'application/json',
        'Authorization': _build_oauth_header('POST', API_URL, consumer_key, consumer_secret, access_token, access_secret)
    }
    req = request.Request(API_URL, data=body, headers=headers, method='POST')
    try:
        with request.urlopen(req) as resp:
            content = resp.read().decode('utf-8')
            result = json.loads(content)
            return result
    except error.HTTPError as http_err:
        detail = http_err.read().decode('utf-8', errors='ignore')
        raise RuntimeError(f"X API error {http_err.code}: {detail}") from http_err


def _append_post_log(entry: Dict):
    records = []
    if POST_LOG.exists():
        try:
            records = json.loads(POST_LOG.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            records = []
    records.append(entry)
    POST_LOG.write_text(json.dumps(records, indent=2), encoding='utf-8')


def _is_already_posted(path: Path) -> bool:
    if not POST_LOG.exists():
        return False
    try:
        records = json.loads(POST_LOG.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return False
    for entry in records:
        if entry.get('post_file') == str(path):
            return True
    return False


def _load_post_log_entries() -> List[Dict]:
    if not POST_LOG.exists():
        return []
    try:
        return json.loads(POST_LOG.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return []


def _parse_timestamp(ts: str) -> Optional[datetime]:
    if not ts:
        return None
    try:
        if ts.endswith('Z'):
            ts = ts[:-1] + '+00:00'
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def _recent_post_count(entries: List[Dict], now: datetime) -> int:
    cutoff = now - timedelta(days=1)
    count = 0
    for entry in entries:
        ts = _parse_timestamp(entry.get('timestamp'))
        if ts and ts >= cutoff:
            count += 1
    return count


def _hours_since_last_post(entries: List[Dict], now: datetime) -> Optional[float]:
    if not entries:
        return None
    latest = max(entries, key=lambda e: e.get('timestamp', ''))
    ts = _parse_timestamp(latest.get('timestamp'))
    if not ts:
        return None
    delta = now - ts
    return delta.total_seconds() / 3600.0


def _parse_dollar_value(raw: str) -> float:
    if not raw:
        return 0.0
    value = raw.replace('$', '').replace(',', '').strip()
    multiplier = 1.0
    if value.endswith(('B', 'M', 'K')):
        suffix = value[-1]
        value = value[:-1]
        if suffix == 'B':
            multiplier = 1_000_000_000
        elif suffix == 'M':
            multiplier = 1_000_000
        elif suffix == 'K':
            multiplier = 1_000
    try:
        return float(value) * multiplier
    except ValueError:
        return 0.0


def _parse_post_entries(text: str) -> List[Dict]:
    entries: List[Dict] = []
    current: Optional[Dict] = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line[0].isdigit() and ' ' in line:
            _, rest = line.split(' ', 1)
            symbol = rest.strip().split()[0].upper()
            current = {'symbol': symbol}
            entries.append(current)
            continue
        if not current:
            continue
        if line.startswith('📈 Momentum:'):
            try:
                value = line.split(':', 1)[1].strip().rstrip('%').replace('+', '')
                current['momentum'] = float(value)
            except (IndexError, ValueError):
                current['momentum'] = 0.0
        elif line.startswith('💰 Volume:'):
            value = line.split(':', 1)[1].strip()
            current['volume'] = _parse_dollar_value(value)
        elif line.startswith('🧭 Trend:'):
            current['trend'] = line.split(':', 1)[1].strip()
    return [entry for entry in entries if 'momentum' in entry and 'volume' in entry]


def _filter_strong_signals(entries: List[Dict]) -> List[Dict]:
    strong = []
    for entry in entries:
        if entry['volume'] >= STRONG_MIN_VOLUME and entry['momentum'] >= STRONG_MIN_MOMENTUM:
            strong.append(entry)
    return strong


def _resolve_queue_dir(state: Dict) -> Path:
    queue_cfg = state.get('queue', {}) or {}
    queue_path = Path(queue_cfg.get('packet_dir') or QUEUE_DEFAULT_DIR)
    queue_path.mkdir(parents=True, exist_ok=True)
    return queue_path


def _latest_packet_path(queue_dir: Path) -> Optional[Path]:
    packets = sorted(queue_dir.glob('packet_*.json'))
    if not packets:
        return None
    return packets[-1]


def _load_packet(path: Path) -> Dict:
    return json.loads(path.read_text(encoding='utf-8'))


def _entries_from_packet(packet: Dict) -> List[Dict]:
    entries: List[Dict] = []
    for entry in packet.get('signals', []):
        symbol = (entry.get('token') or '').upper()
        if not symbol:
            continue
        momentum = float(entry.get('momentum_pct', entry.get('momentum', 0.0)) or 0.0)
        volume = float(entry.get('volume_usd', entry.get('volume', 0.0)) or 0.0)
        trend = (entry.get('momentum_trend') or entry.get('trend') or 'steady').title()
        entries.append({
            'symbol': symbol,
            'momentum': momentum,
            'volume': volume,
            'trend': trend
        })
    return entries


def _format_dollars(amount: float) -> str:
    if amount >= 1_000_000_000:
        return f"${amount / 1_000_000_000:.1f}B"
    if amount >= 1_000_000:
        return f"${amount / 1_000_000:.0f}M"
    if amount >= 1_000:
        return f"${amount / 1_000:.0f}K"
    return f"${amount:.0f}"


def _describe_regime(selected: List[Dict]) -> str:
    avg_momentum = sum(entry['momentum'] for entry in selected) / len(selected)
    if avg_momentum >= 25:
        return "momentum squeeze in liquid names"
    if avg_momentum >= 15:
        return "rotation into high-liquidity leaders"
    return "measured risk-on flow focused on majors"


def _compose_tweet(selected: List[Dict]) -> str:
    hook = f"Market Radar: {_describe_regime(selected)}."
    lines = [hook]
    for entry in selected:
        trend = entry.get('trend', 'Steady').lower()
        lines.append(
            f"- {entry['symbol']} {entry['momentum']:+.1f}% | {_format_dollars(entry['volume'])} vol ({trend})"
        )
    return "\n".join(lines)


def x_autoposter():
    ops_state = load_ops_state()
    channel_cfg = (ops_state.get('channels') or {}).get(CHANNEL_NAME, {})
    if not channel_cfg.get('enabled'):
        return {
            'message': 'Skipped: x_autoposter disabled in ops_state',
            'tweet_id': None,
            'post_file': None,
            'packet_path': None
        }
    if bool(ops_state.get('draft_only', True)):
        return {
            'message': 'Skipped: ops_state is in draft_only mode',
            'tweet_id': None,
            'post_file': None,
            'packet_path': None
        }
    mode = (channel_cfg.get('mode') or 'manual').lower()
    if mode != 'auto':
        return {
            'message': f'Skipped: channel mode is {mode}, not auto',
            'tweet_id': None,
            'post_file': None,
            'packet_path': None
        }

    queue_dir = _resolve_queue_dir(ops_state)
    packet_path_obj = _latest_packet_path(queue_dir)
    if not packet_path_obj:
        return {
            'message': 'Skipped: no market_radar packets available',
            'tweet_id': None,
            'post_file': None,
            'packet_path': None
        }
    packet = _load_packet(packet_path_obj)
    packet_status = (packet.get('status') or 'draft').lower()
    if packet_status != 'ready':
        return {
            'message': f'Skipped: latest packet still {packet_status}',
            'tweet_id': None,
            'post_file': None,
            'packet_path': str(packet_path_obj)
        }
    packet_channels = packet.get('channels') or []
    if CHANNEL_NAME not in packet_channels:
        return {
            'message': 'Skipped: packet not targeting x_autoposter',
            'tweet_id': None,
            'post_file': None,
            'packet_path': str(packet_path_obj)
        }

    post_file_path = packet.get('assets', {}).get('raw_post_path')
    post_path_obj = Path(post_file_path) if post_file_path else _latest_post_file()

    now = datetime.now(timezone.utc)
    log_entries = _load_post_log_entries()
    if _recent_post_count(log_entries, now) >= MAX_POSTS_PER_DAY:
        return {
            'message': 'Skipped: daily X post cap reached',
            'tweet_id': None,
            'post_file': str(post_path_obj),
            'packet_path': str(packet_path_obj)
        }
    hours_since = _hours_since_last_post(log_entries, now)
    if hours_since is not None and hours_since < MIN_POST_SPACING_HOURS:
        return {
            'message': f'Skipped: spacing {hours_since:.1f}h < {MIN_POST_SPACING_HOURS}h requirement',
            'tweet_id': None,
            'post_file': str(post_path_obj),
            'packet_path': str(packet_path_obj)
        }

    if _is_already_posted(post_path_obj):
        return {
            'message': 'Latest post already tweeted',
            'post_file': str(post_path_obj),
            'tweet_id': None,
            'packet_path': str(packet_path_obj)
        }

    entries = _entries_from_packet(packet)
    if not entries:
        text = _read_post_text(post_path_obj)
        entries = _parse_post_entries(text)

    strong_entries = _filter_strong_signals(entries)
    if len(strong_entries) < 2:
        return {
            'message': 'Skipped: fewer than two strong high-liquidity signals',
            'post_file': str(post_path_obj),
            'tweet_id': None,
            'packet_path': str(packet_path_obj)
        }

    selected = strong_entries[:3]
    tweet_text = _compose_tweet(selected)

    response = _send_tweet(tweet_text)
    data = response.get('data') or {}
    tweet_id = data.get('id')
    if not tweet_id:
        raise RuntimeError(f"Unexpected response from X API: {response}")

    timestamp = now.strftime('%Y-%m-%dT%H:%M:%SZ')
    log_entry = {
        'tweet_id': tweet_id,
        'timestamp': timestamp,
        'post_file': str(post_path_obj),
        'packet_path': str(packet_path_obj),
        'text_preview': tweet_text[:120]
    }
    _append_post_log(log_entry)

    confirmation = {
        'message': 'Tweet posted successfully',
        'tweet_id': tweet_id,
        'post_file': str(post_path_obj),
        'packet_path': str(packet_path_obj)
    }
    return confirmation


if __name__ == '__main__':
    result = x_autoposter()
    if result.get('tweet_id'):
        print(f"X post sent: {result['tweet_id']} from {result['post_file']}")
    else:
        print(f"No X post needed: {result['message']} ({result['post_file']})")
