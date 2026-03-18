import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from ops_state import enabled_channel_names, load_ops_state

LOG_DIR = "/data/.openclaw/workspace/market_logs"
OUTPUT_DIR = "/data/.openclaw/workspace/x_posts"
QUEUE_DEFAULT_DIR = Path("/data/.openclaw/workspace/queues/market_radar")
MAX_THREAD_POSTS = 4
TOP_N = 3
RANK_EMOJIS = ["1️⃣", "2️⃣", "3️⃣"]


def _resolve_queue_dir(ops_state: Dict) -> Tuple[Path, int]:
    queue_cfg = ops_state.get("queue", {}) or {}
    queue_path = Path(queue_cfg.get("packet_dir") or QUEUE_DEFAULT_DIR)
    queue_path.mkdir(parents=True, exist_ok=True)
    retention = int(queue_cfg.get("retention_minutes", 120) or 120)
    return queue_path, retention


def _write_packet(queue_dir: Path, packet_stamp: str, payload: Dict) -> str:
    path = queue_dir / f"packet_{packet_stamp}.json"
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    return str(path)

def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _describe_regime(entries: List[Dict]) -> str:
    if not entries:
        return "No qualified signals"
    sample = entries[:TOP_N]
    avg_momentum = sum(_safe_float(item.get('momentum')) for item in sample) / len(sample)
    big_liq = sum(1 for item in sample if _safe_float(item.get('volume')) >= 25_000_000)
    accelerating = any(str(item.get('momentum_trend', '')).lower() == 'accelerating' for item in sample)
    if big_liq >= 2 and avg_momentum >= 30:
        return "Momentum squeeze in liquid names"
    if accelerating and avg_momentum >= 15:
        return "Rotation into high-beta leaders"
    if avg_momentum <= 5:
        return "Chop — patience required"
    return "Measured risk-on flow"


def _liquidity_bucket(volume: float) -> str:
    if volume >= 50_000_000:
        return "deep"
    if volume >= 10_000_000:
        return "liquid"
    if volume >= 2_000_000:
        return "thin"
    return "micro"


def _persistence_label(persistence: int) -> str:
    if persistence >= 4:
        return "sticky"
    if persistence >= 2:
        return "building"
    return "fresh"


def _caution_line(entries: List[Dict]) -> str:
    sample = entries[:TOP_N]
    buckets = [_liquidity_bucket(_safe_float(item.get('volume'))) for item in sample]
    micro_count = buckets.count('micro')
    thin_count = buckets.count('thin')
    if micro_count >= 2:
        return "⚠️ Mostly micro caps — size down."
    if micro_count == 1 or thin_count >= 2:
        return "⚠️ Mixed liquidity — pick spots."
    return "⚠️ Liquid leaders — momentum is stretched."


def _load_latest_entries() -> List[Dict]:
    if not os.path.isdir(LOG_DIR):
        raise FileNotFoundError(f"Log directory not found: {LOG_DIR}")

    json_logs = sorted(
        [f for f in os.listdir(LOG_DIR) if f.endswith(".jsonl")],
        reverse=True
    )
    if not json_logs:
        raise FileNotFoundError("No .jsonl logs found. Run the upgraded market_scanner at least once.")

    latest_path = os.path.join(LOG_DIR, json_logs[0])
    entries = []
    with open(latest_path, "r") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if not entries:
        raise ValueError(f"No JSON entries present in {latest_path}")

    entries_by_ts: Dict[str, List[Dict]] = {}
    for entry in entries:
        ts = entry.get("timestamp")
        if not ts:
            continue
        entries_by_ts.setdefault(ts, []).append(entry)

    if not entries_by_ts:
        raise ValueError(f"Timestamped entries missing in {latest_path}")

    latest_ts = sorted(entries_by_ts.keys())[-1]
    latest_entries = entries_by_ts[latest_ts]
    for entry in latest_entries:
        entry.setdefault("score", 0)
        entry.setdefault("momentum", 0)
        entry.setdefault("volume", 0)
        entry.setdefault("persistence", 1)
        entry.setdefault("status", "new")

    ranked = sorted(latest_entries, key=lambda e: e.get("score", 0), reverse=True)
    return ranked[:TOP_N], latest_ts, len(latest_entries)

def _format_number(value: float) -> str:
    if value >= 1_000_000_000:
        return f"{value/1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"{value/1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value/1_000:.1f}K"
    return f"{value:.0f}"


def _build_post(ranked: List[Dict], timestamp: str, total_signals: int, regime_line: Optional[str] = None) -> str:
    if not ranked:
        return "📊 Market Radar\n\nNo qualified signals in the latest scan."

    dt = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M")
    regime_snapshot = regime_line or _describe_regime(ranked)
    lines = [
        "📊 Market Radar",
        f"Regime: {regime_snapshot}",
        f"Last scan: {dt.strftime('%H:%M %d %b')}",
        f"Signals detected: {total_signals}",
        "",
        "🔥 Top opportunities:",
        ""
    ]
    for idx, entry in enumerate(ranked[:TOP_N]):
        token = entry.get("token", "?")
        momentum = entry.get("momentum", 0.0)
        volume = entry.get("volume", 0.0)
        persistence = int(entry.get("persistence", 1) or 1)
        trend = (entry.get("momentum_trend") or "steady").replace("_", " ").title()
        emoji = RANK_EMOJIS[idx] if idx < len(RANK_EMOJIS) else f"{idx+1}."
        liquidity_note = _liquidity_bucket(_safe_float(volume))
        persistence_note = _persistence_label(persistence)
        block = [
            f"{emoji} {token}",
            f"   📈 Momentum: {momentum:+.1f}%",
            f"   💰 Volume: ${_format_number(volume)} ({liquidity_note})",
            f"   ♻️ Persistence: {persistence} scans ({persistence_note})",
            f"   🧭 Trend: {trend}"
        ]
        lines.extend(block + [""])

    caution = _caution_line(ranked)
    if caution:
        lines.append(caution)
        lines.append("")

    lines.append("Scanner runs every 60 seconds.")
    return "\n".join(lines).strip()


def _build_thread(ranked: List[Dict], timestamp: str) -> List[str]:
    if not ranked:
        return []

    dt = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M")
    posts = [f"Market radar update. Latest scan: {dt.strftime('%H:%M %d %b')}."]

    for idx, entry in enumerate(ranked[:3], start=1):
        if len(posts) >= MAX_THREAD_POSTS:
            break
        token = entry.get("token", "?")
        momentum = entry.get("momentum", 0.0)
        volume = entry.get("volume", 0.0)
        persistence = entry.get("persistence", 1)
        status = entry.get("status", "new").capitalize()
        post = (
            f"Breakdown #{idx}: {token}\n"
            f"Momentum: {momentum:+.2f}%\n"
            f"Volume spike: ${_format_number(volume)}\n"
            f"Persistence: {persistence} scans\n"
            f"Signal: {status}"
        )
        posts.append(post[:280])

    while len(posts) < MAX_THREAD_POSTS:
        posts.append("Additional breakdown unavailable.")

    return posts[:MAX_THREAD_POSTS]


def _write_output(filename: str, lines: List[str]):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w") as handle:
        handle.write("\n".join(lines).strip() + "\n")
    return path


def market_broadcaster():
    ranked, timestamp, total_signals = _load_latest_entries()
    dt = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M")
    suffix = dt.strftime("%Y_%m_%d_%H%M")

    regime_line = _describe_regime(ranked)
    post_text = _build_post(ranked, timestamp, total_signals, regime_line=regime_line)
    post_path = _write_output(f"post_{suffix}.txt", [post_text])

    thread_posts = _build_thread(ranked, timestamp)
    thread_path = None
    if thread_posts:
        thread_path = _write_output(f"thread_{suffix}.txt", thread_posts)

    ops_state = load_ops_state()
    ops_snapshot = {
        "draft_only": bool(ops_state.get("draft_only", True)),
        "enabled_channels": enabled_channel_names(ops_state),
        "channel_configs": ops_state.get("channels", {}),
    }

    queue_dir, retention_minutes = _resolve_queue_dir(ops_state)
    packet_stamp = f"{dt.strftime('%Y%m%dT%H%M')}Z"
    created_at = datetime.now(timezone.utc)
    expires_at = created_at + timedelta(minutes=retention_minutes)
    status = "draft" if ops_snapshot["draft_only"] else "ready"
    packet_payload = {
        "packet_id": f"market_radar::{packet_stamp}",
        "created_at": created_at.strftime('%Y-%m-%dT%H:%M:%SZ'),
        "source_task": "market_broadcaster",
        "status": status,
        "expires_at": expires_at.strftime('%Y-%m-%dT%H:%M:%SZ'),
        "channels": ops_snapshot["enabled_channels"],
        "channel_snapshot": ops_snapshot["channel_configs"],
        "assets": {
            "headline": post_text,
            "thread": thread_posts,
            "raw_post_path": post_path,
            "raw_thread_path": thread_path,
        },
        "signals": ranked,
        "meta": {
            "total_signals": total_signals,
            "top_ranked_count": len(ranked),
            "scan_timestamp": timestamp,
            "regime": regime_line,
        }
    }
    packet_path = _write_packet(queue_dir, packet_stamp, packet_payload)

    return {
        "timestamp": timestamp,
        "top_ranked": ranked,
        "post_path": post_path,
        "thread_path": thread_path,
        "thread_posts": thread_posts,
        "post_text": post_text,
        "ops_state": ops_snapshot,
        "packet_path": packet_path
    }


if __name__ == "__main__":
    result = market_broadcaster()
    print(json.dumps(result, indent=2))
