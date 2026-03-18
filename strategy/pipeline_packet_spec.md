# Market Pipeline Packet Spec (Step 1)

## Objectives
- Decouple the signal producer (market pipeline) from any downstream channel logic.
- Provide a single, typed packet format that every consumer (X autoposter, Telegram, email, etc.) can read without touching the core pipeline.
- Preserve full auditability by keeping generated copy + structured data together.

## File Layout Proposal
```
/data/.openclaw/workspace/
├── queues/
│   └── market_radar/
│       ├── packet_20260318T033100Z.json
│       └── ...
├── x_posts/ (legacy text artifacts remain for now)
└── ops_state.yaml (coming in step 2)
```
- `queues/market_radar/` holds JSON packets, one per scanner cycle that produced qualified signals.
- Packet filenames include the UTC timestamp to keep ordering deterministic.
- Consumers move packets by writing a sibling `.done` file or dropping a record into their own state log—no deletions required.

## Packet Schema (draft v0.1)
Each `packet_*.json` contains a single JSON object:

| Field | Type | Notes |
| --- | --- | --- |
| `packet_id` | string | `market_radar::<timestamp>`
| `created_at` | string (ISO8601 UTC) | When the packet was assembled.
| `source_task` | string | e.g. `market_broadcaster`.
| `status` | string | `draft`, `ready`, or `consumed`. Producer writes `draft`, any consumer that completes its work may overwrite a sibling `.meta` later.
| `expires_at` | string (ISO8601) | Optional TTL so consumers can skip stale packets.
| `channels` | array of strings | Intended downstream targets, e.g. `["x_autoposter", "telegram"]`. Controlled via `ops_state.yaml` later.
| `assets` | object | Text artifacts keyed by role.
| `signals` | array<object> | Structured representation of the ranked tokens.
| `meta` | object | Counts, metrics, or summary info.

Sub-structures:

### `assets`
```
"assets": {
  "headline": "📊 Market Radar...",
  "thread": ["Market radar update...", "Breakdown #1 ..."],
  "raw_post_path": "/data/.openclaw/workspace/x_posts/post_2026_03_18_0331.txt",
  "raw_thread_path": "/data/.openclaw/workspace/x_posts/thread_2026_03_18_0331.txt"
}
```
- Keep existing plaintext files as-is for backwards compatibility. Consumers can either read `assets.headline` directly or open the referenced file.

### `signals`
Each entry contains the fields already available inside `market_logs/2026-03-18.jsonl`:
```
{
  "token": "SIREN",
  "score": 0.24985,
  "momentum_pct": 28.09,
  "volume_usd": 42800000.0,
  "persistence_scans": 4,
  "status": "new",
  "momentum_trend": "steady",
  "liquidity_health": 0.5,
  "momentum_alignment_score": 0.5,
  "volume_score": 0.0724,
  "timestamp": "2026-03-18T01:29"
}
```
Additional derived fields (e.g., USD volume buckets, “strength” labels) can ride along so consumers never have to recalc.

### `meta`
```
{
  "total_signals": 79,
  "top_ranked_count": 3,
  "scan_timestamp": "2026-03-18T01:29",
  "generator_version": "market_broadcaster@hash",
  "notes": "Scanner runs every 60 seconds"
}
```

## Data Audit (Current State)
| Source | Path | Verified Fields |
| --- | --- | --- |
| Ranked signals | `market_logs/2026-03-18.jsonl` | `token`, `timestamp`, `volume`, `momentum`, `persistence`, `status`, `momentum_trend`, alignment & score components. ✅
| Generated copy | `x_posts/post_*.txt`, `x_posts/thread_*.txt` | Headline + breakdown text. ✅ (multiple samples inspected, latest `post_2026_03_18_0331.txt`).
| X autoposter inputs | `skills/x-autoposter/x_autoposter.py` | Already parses volume/momentum from the post files—matches the schema above. ✅
| System logs | `system_logs/autonomous_market_loop.log` | Not required for packets but available for tracing. ✅

Conclusion: all fields required for the packet schema already exist in the latest pipeline artifacts. No code changes yet—this step simply nails down the structure. Next step will be adding `ops_state.yaml` and the queue writer in `market_broadcaster` so packets are emitted alongside the legacy files.

## Manual Review Hook
- New skill `skills/telegram_queue_consumer/telegram_queue_consumer.py` reads the latest packet, mirrors the headline, and writes human-ready drafts to `/queues/market_radar/drafts/telegram_<stamp>.txt`.
- Use this while external channels stay disabled: run `python3 skills/telegram_queue_consumer/telegram_queue_consumer.py` after a scan to refresh the draft.
- Future consumers can follow the same pattern: load `ops_state`, pick the queue directory, and emit channel-specific drafts without touching live APIs.
