---
name: market_scanner
version: 0.1.0
description: Scan new tokens for high volume and momentum, compare against the last 5 runs, and log only new or strengthening signals to /data/.openclaw/workspace/market_logs/YYYY-MM-DD.csv with top-opportunity rankings.
entrypoint: market_scanner.py
methods:
  - name: market_scanner
    args:
      - name: tokens
        type: list
      - name: volume_data
        type: dict
      - name: momentum_data
        type: dict
    description: |-
      Scan tokens for those with high volume and momentum; log to CSV if thresholds are met.
    returns: list of matching log entries
manifest:
  tool:
    name: market_scanner
    function: market_scanner
    description: Scan new tokens for high volume and momentum; log them.
    args:
      tokens: list of tokens
      volume_data: dict of token:volume
      momentum_data: dict of token:momentum
    returns: list of matching log entries
---

# market_scanner Skill

Use this skill to surface only the strongest crypto signals:

1. Provide token symbols plus corresponding `volume_data` (USD) and `momentum_data` (percentage change). Thresholds default to 100,000 USD volume and 5% momentum.
2. Each run loads the last 5 scans from `/data/.openclaw/workspace/market_logs/YYYY-MM-DD.jsonl`, tracks per-token performance, and filters out repeated weak entries (those that fail to improve on both volume and momentum).
3. Only **new** or **strengthening** tokens are logged (one JSON line per entry) with timestamp, volume, momentum, status, persistence count, composite-score inputs, liquidity health metrics, and **multi-timeframe momentum fields** (`momentum_5m`, `15m`, `60m`, `momentum_alignment_score`, trend label).
4. The function returns a list where the first element is a `SUMMARY:{...}` JSON blob (top opportunities with momentum trend). When the DEX pipeline produces candidates, a second `DEX_SUMMARY:{...}` item is included with the top five DEX names.
5. Every run also queries `https://api.dexscreener.com/latest/dex/pairs`, filters for:
   - liquidity > $50k
   - 24h volume > $100k
   - pair age < 48h
   - positive 24h price change
   Scores are computed from volume spikes, liquidity strength, buy pressure, and saved to `/data/.openclaw/workspace/market_scanner/candidates.json` for downstream rankers.

Additional scoring now includes:
- Liquidity-health factor (10‑minute volume trend, buy/sell proxy, volume acceleration)
- Multi-timeframe momentum alignment (5/15/60 min deltas → accelerating / steady / fading / isolated spike labels)

Use this workflow when you need rolling context, deduplication of stale mentions, prioritized highlights for CEX-listed assets, plus a fresh stream of high-performing DEX pairs ready for additional ranking logic.
