---
name: paper-trader
description: Simulate $100 paper trades from the latest market_scanner rankings, maintain open/closed logs, and report PnL with +8% TP / -4% SL risk rules.
entrypoint: paper_trader.py
methods:
  - name: paper_trader
    args: []
    description: Read the newest market_scanner log, update existing paper trades, close hits, open new $100 positions for top 5 tokens, and emit a summary plus JSON logs.
    returns: dict containing timestamp, open positions, closed trades, summary, and file paths
---

# Paper Trader

## Workflow

1. **Ingest ranked signals** – Loads the newest `/data/.openclaw/workspace/market_logs/*.jsonl` file, grabs the most recent timestamp, and sorts entries by `score`, keeping the top 5 tokens.
2. **Fetch live prices** – Pulls current USD prices from CoinGecko's `coins/markets` endpoint (same universe as market_scanner) so each trade uses the price at signal time.
3. **Manage open positions**
   - Position size: `$100` per trade.
   - Take profit: `+8%` from entry.
   - Stop loss: `-4%` from entry.
   - Every run refreshes PnL using the latest price map, marks TP/SL hits, and closes them with timestamps and exit prices.
4. **Open new trades** – Any ranked token not already open gets a fresh position with stored entry time, price, TP/SL levels, and persistence metadata from the scanner.
5. **Persist state**
   - `/data/.openclaw/workspace/paper_trades/open_positions.json` – array of live trades (entry/target/stop/current price/pnl/last_update).
   - `/data/.openclaw/workspace/paper_trades/trades_log.json` – append-only history of closed trades (created as `[]` if no exits yet).
6. **Return summary** – Human-readable block:
   ```
   Paper trading update

   Open positions:
   ETH +2.10%
   ...

   Closed trades:
   AAVE +8.00% (TP hit)
   PEPE -4.00% (SL hit)
   ```
   plus the structured JSON payload for downstream automation.

## Implementation Notes

- Keep the exported `paper_trader()` method in sync with `autonomous_market_loop.py`; that runner loads the module dynamically and calls `module.paper_trader()`. Renaming or removing this function will break the pipeline.

## Error Handling & Notes

- Raises descriptive errors if no `.jsonl` logs exist or the log lacks JSON entries.
- Price fetch covers up to the top 250 volume symbols; if a token isn't returned, its open trade is left untouched until data becomes available.
- Thread-safe (single-writer) JSON persistence—each run rewrites the full JSON files to avoid partial writes.
