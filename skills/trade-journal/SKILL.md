---
name: trade-journal
description: Convert paper_trader closes into a structured journal + summary stats for performance analysis.
entrypoint: trade_journal.py
methods:
  - name: trade_journal
    args: []
    description: Read trades_log.json, refresh trade_journal/journal.json, and return win/gain/loss/drawdown/source stats.
    returns: dict of summary statistics
---

# Trade Journal

## Workflow

1. Load all completed trades from `/data/.openclaw/workspace/paper_trades/trades_log.json`.
2. For each trade, capture:
   - symbol (`token`), entry/exit prices, position size
   - `% PnL`
   - trade duration (hours)
   - `signal_source` and `market_condition` (defaults: `market_scanner` / `unknown` if missing)
3. Save the structured entries to `/data/.openclaw/workspace/trade_journal/journal.json` for downstream analysis.
4. Compute summary metrics:
   - Win rate
   - Average gain / average loss
   - Max drawdown (based on cumulative PnL sequence)
   - Best signal source (highest average PnL)
5. Return the statistics dict so you can display/report it immediately.

## Notes

- Only trades with both `exit_price` and `exit_time` are journaled.
- The journal file overwrites with the latest snapshot each run; keep older versions if needed.
- You can later extend trades_log entries with `signal_source` / `market_condition` fields so this journal reflects the richer metadata.
