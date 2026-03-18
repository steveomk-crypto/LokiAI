---
name: performance-analyzer
description: Review paper_trader results, compute PnL metrics, and write performance reports + strategy notes to /data/.openclaw/workspace/performance_reports/.
entrypoint: performance_analyzer.py
methods:
  - name: performance_analyzer
    args: []
    description: Aggregate closed-trade stats, summarize open positions, judge thresholds, and emit timestamped/"latest" reports.
    returns: dict with computed metrics, token leaderboards, open positions, and report paths
  - name: journal_performance
    args: []
    description: Analyze trade_journal/journal.json, detect profitable patterns, rank symbols/sources, and save to performance_report.json.
    returns: dict with stats, ranking arrays, and report_path
---

# Performance Analyzer

## Paper-Trader Snapshot (legacy workflow)

1. Ensure `paper_trader` has created:
   - `/data/.openclaw/workspace/paper_trades/trades_log.json`
   - `/data/.openclaw/workspace/paper_trades/open_positions.json`
2. Run `performance_analyzer.performance_analyzer()`.
   - Computes total trades, win rate, average win/loss %, cumulative PnL %, TP/SL counts, best/worst tokens, and lists current positions.
   - Writes `report_YYYY_MM_DD_HHMM.txt` plus `summary_latest.txt` under `/performance_reports/`.
   - Returns the structured metrics + file paths for downstream automation.

## Trade-Journal Intelligence (new)

1. Make sure `trade_journal/journal.json` exists (populate via `trade_journal.trade_journal()`).
2. Run `performance_analyzer.journal_performance()`.
   - Loads the journal and computes overall win rate, average gain/loss, max drawdown.
   - Ranks best/worst symbols, best signal sources, and flags signals that consistently win/lose (≥70% / ≤30% win rates).
   - Buckets trade durations (<1h, 1–6h, >6h) to identify the most profitable timeframes.
   - Saves the analysis to `/data/.openclaw/workspace/trade_journal/performance_report.json` and returns a dict with:
     ```json
     {
       "best_signal_sources": [["market_scanner", 4.2], ...],
       "worst_signal_sources": [...],
       "profitable_symbols": [...],
       "losing_symbols": [...],
       "winning_signals": [...],
       "duration_trends": [...],
       "report_path": ".../performance_report.json"
     }
     ```

Use the journal analysis whenever you want deeper pattern detection (e.g., which signals or durations drive edge) while keeping the original paper-trader snapshot workflow intact.
