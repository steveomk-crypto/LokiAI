---
name: risk-manager
description: Gate new paper trades using position limits, loss streaks, drawdown, and signal quality before paper_trader opens a position.
entrypoint: risk_manager.py
methods:
  - name: risk_manager
    args:
      - name: signal
        type: dict (optional)
      - name: account_size
        type: float (optional)
    description: Evaluate whether a new trade is allowed; returns APPROVED/BLOCKED plus reasons, and logs the decision.
    returns: dict with decision, reasons, open_positions, consecutive_losses, daily_drawdown_pct
---

# Risk Manager

## Inputs

- `paper_trades/open_positions.json` – current live trades.
- `paper_trades/trades_log.json` – historical closed trades with `pnl_percent` and `exit_time`.
- Optional `signal` dict when calling the method:
  ```python
  {
    "token": "ETH",
    "persistence": 3,
    "score": 0.52,   # ranking confidence from market_scanner
    "risk_usd": 100  # planned dollar risk for the new trade
  }
  ```
- Optional `account_size` (defaults to $10,000) to map the 1% risk rule to USD.

## Risk Rules

1. **Max open positions**: block when ≥10 live trades.
2. **Risk per trade**: `risk_usd` must be ≤ 1% of `account_size` (defaults to $100 when not supplied).
3. **Loss streak**: block after 3 consecutive losing trades (based on `pnl_percent`).
4. **Daily drawdown**: sum of today’s closed PnL must stay above –5%; breaching it halts new entries for the day.
5. **Signal quality**: persistence must be ≥1 and confidence (score) ≥0.30 (tune as needed).

## Output

- Returns a dict, e.g. `{"decision": "BLOCKED", "reasons": ["Max open positions reached"], ...}`.
- Appends every decision to `/data/.openclaw/workspace/risk_logs/risk_decisions.json` with a timestamp, so the supervisory trail is preserved.

Use this skill immediately before opening a new trade: pass the candidate signal (persistence/score/risk) and let it enforce the guardrails. If the decision is `BLOCKED`, respect the reason and skip the entry; otherwise proceed with paper_trader.
