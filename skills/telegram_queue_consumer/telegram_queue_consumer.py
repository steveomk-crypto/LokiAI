import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from ops_state import load_ops_state

QUEUE_FALLBACK = Path("/data/.openclaw/workspace/queues/market_radar")
DRAFTS_DIR = QUEUE_FALLBACK / "drafts"


def _resolve_queue_dir(state: Dict) -> Path:
    queue_cfg = state.get('queue', {}) or {}
    queue_path = Path(queue_cfg.get('packet_dir') or QUEUE_FALLBACK)
    queue_path.mkdir(parents=True, exist_ok=True)
    return queue_path


def _latest_packet_path(queue_dir: Path) -> Optional[Path]:
    packets = sorted(queue_dir.glob("packet_*.json"))
    if not packets:
        return None
    return packets[-1]


def _format_usd(value: float) -> str:
    abs_val = abs(value)
    if abs_val >= 1_000_000_000:
        formatted = f"${abs_val/1_000_000_000:.1f}B"
    elif abs_val >= 1_000_000:
        formatted = f"${abs_val/1_000_000:.1f}M"
    elif abs_val >= 1_000:
        formatted = f"${abs_val/1_000:.1f}K"
    else:
        formatted = f"${abs_val:,.0f}"
    if value < 0:
        return f"-{formatted}"
    return formatted


def telegram_queue_consumer():
    state = load_ops_state()
    queue_dir = _resolve_queue_dir(state)
    packet_path = _latest_packet_path(queue_dir)
    if not packet_path:
        return {
            'status': 'empty',
            'message': 'No packets available',
            'draft_path': None
        }

    packet = json.loads(packet_path.read_text(encoding='utf-8'))
    packet_id = packet.get('packet_id') or packet_path.stem
    stamp = packet_id.split('::')[-1]
    created_at = packet.get('created_at') or datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    scan_ts = packet.get('meta', {}).get('scan_timestamp') or 'n/a'
    status = packet.get('status', 'draft')
    headline = packet.get('assets', {}).get('headline')

    lines = [
        "Telegram Draft — Market Radar",
        f"Packet: {packet_id}",
        f"Scan: {scan_ts}",
        f"Packet status: {status}",
        f"Created: {created_at}",
        ""
    ]

    if headline:
        lines.append(headline)
        lines.append("")

    lines.append("Top breakdowns:")
    for entry in packet.get('signals', [])[:3]:
        token = entry.get('token', '?')
        momentum = entry.get('momentum_pct', entry.get('momentum'))
        volume = entry.get('volume_usd', entry.get('volume'))
        trend = entry.get('momentum_trend') or entry.get('status') or 'n/a'
        try:
            momentum_val = float(momentum)
        except (TypeError, ValueError):
            momentum_val = 0.0
        try:
            volume_val = float(volume)
        except (TypeError, ValueError):
            volume_val = 0.0
        lines.append(
            f"- {token}: {momentum_val:+.1f}% | {_format_usd(volume_val)} vol | {trend}"
        )

    lines.append("")
    lines.append("Draft only — send manually after review.")

    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    draft_path = DRAFTS_DIR / f"telegram_{stamp}.txt"
    draft_path.write_text("\n".join(lines).strip() + "\n", encoding='utf-8')

    return {
        'status': 'ok',
        'message': 'Telegram draft prepared',
        'draft_path': str(draft_path),
        'packet_path': str(packet_path)
    }


if __name__ == "__main__":
    result = telegram_queue_consumer()
    print(json.dumps(result, indent=2))
