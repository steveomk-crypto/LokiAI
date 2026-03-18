---
name: trade-analytics
description: Generate trade performance breakdowns by signal attributes (persistence, exit reason, hold time) using the trade log. Run when you need post-run analytics or want to inspect how specific filters affect win rate/PnL.
---

# Trade Analytics Skill

Use this skill whenever you need a structured breakdown of paper_trader performance. It reads `paper_trades/trades_log.json`, computes hold times, aggregates stats, and drops a Markdown report in `performance_reports/` so you can diff runs over time.

## Quick Start

1. Execute the script:
   ```bash
   PYTHONPATH=/data/.openclaw/workspace python3 skills/trade-analytics/scripts/run_attribute_breakdown.py
   ```
2. The script prints a JSON summary and writes a file such as `performance_reports/attribute_breakdown_2026-03-17T0805Z.md`.
3. Review the "Overall", "By Persistence", and "By Exit Reason" sections to spot which signals or exit modes need tuning.

## Report Contents

- **Overall:** total trades, win rate, average PnL, median hold hours.
- **By Persistence:** bucketed stats per persistence level to validate the new entry filter.
- **By Exit Reason:** highlights what’s causing exits (TP, trailing, time-stop, loser control, etc.).

Run this after any meaningful batch of closes (e.g., at the end of the day or after a config change) to keep a rolling knowledge base of what’s working.
