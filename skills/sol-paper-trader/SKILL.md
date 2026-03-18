---
name: sol-paper-trader
description: Run $3 Solana-only paper trades using Birdeye data, hold max 5 slots, and log PnL with +8% TP / -4% SL / 4h time stop.
entrypoint: sol_paper_trader.py
methods:
  - name: sol_paper_trader
    args: []
    description: Fetch top Solana tokens from Birdeye, update the $3 paper book (max 5 trades), close hits, open new entries, and return a summary payload.
    returns: dict with timestamp, open_positions, closed_trades, summary, and file paths
---

# Sol Paper Trader

This skill keeps a lightweight Solana-focused paper portfolio so we can track meme/LST momentum separately from the CEX book.

## Inputs & data sources

- **Birdeye API (requires `BIRDEYE_API_KEY`)** – queries `https://public-api.birdeye.so/defi/v3/token/list` for the top-volume Solana tokens and falls back to `token_overview` for any open names that fall off the list.
- **State files** (created under `/data/.openclaw/workspace/sol_paper_trades/`):
  - `open_positions.json`
  - `trades_log.json`

## Trading rules

- Position size: **$3** per entry.
- Risk envelope: **+8% take profit**, **-4% stop loss**, and a **4-hour time stop** if |PnL| < 1%.
- Slot cap: **5 concurrent positions**. New entries only fill when a slot is free.
- Universe filter: tokens on Solana with ≥$250k 24h volume, ≥$50k liquidity, and not on the stable/LST blocklist.

## Outputs

The method returns a dict with:

- `timestamp`
- `open_positions` (list)
- `closed_trades` (list)
- `summary` (human-readable text for DM/console)
- `open_positions_path`, `trades_log_path`

The files are overwritten atomically each run so other skills can read them safely. Run this every few minutes for mark-to-market updates, and optionally schedule an hourly job with announcements enabled for PnL summaries.
