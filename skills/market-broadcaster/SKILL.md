---
name: market-broadcaster
description: Turn the latest market_scanner rankings into ready-to-post X updates (Market Radar post + 4-part thread) based on the newest log file in /data/.openclaw/workspace/market_logs.
entrypoint: market_broadcaster.py
methods:
  - name: market_broadcaster
    args: []
    description: Read the newest market_scanner log, pick the top 3 ranked tokens, and write both the Market Radar post and 4-part breakdown thread to /data/.openclaw/workspace/x_posts/.
    returns: dict with ranked data, generated copy, and file paths
---

# Market Broadcaster

## Quick Start

1. Confirm the upgraded `market_scanner` has produced at least one `.jsonl` log in `/data/.openclaw/workspace/market_logs/`.
2. Run `market_broadcaster.market_broadcaster()` (no args). The script will:
   - Load the newest log file and grab the most recent timestamped run.
   - Sort entries by the `score` field and keep the top 3 tokens.
   - Produce the mandated Market Radar post:
     ```
     🚨 Market Radar

     Strength detected in:

     1️⃣ TOKEN
     Momentum: +X.X%
     Volume spike: $X
     Persistence: Y scans

     ... (tokens 2 & 3)

     Scanner runs every 2 minutes.
     ```
   - Produce a **4-post thread**:
     1. "Market radar update. Latest scan: <time>."
     2-4. One post per token (“Breakdown #n: …” with momentum, volume spike value, persistence, and signal status).
   - Save outputs to `/data/.openclaw/workspace/x_posts/` as `post_YYYY_MM_DD_HHMM.txt` and `thread_YYYY_MM_DD_HHMM.txt`.
3. Inspect the returned dict for direct reuse (timestamp, ranked token data, generated strings, and file paths).

## Error Handling & Notes

- Raises a descriptive error if no `.jsonl` logs exist or a log has no JSON entries.
- Thread always contains 4 posts; if fewer than 3 tokens are available, remaining slots become “additional breakdown unavailable” placeholders.
- All posts stay <280 characters and avoid extra hashtags/emoji beyond the specified template.
