---
name: position-manager
description: Automate trailing stops, partial exits, loser control, and time-based closes for paper_trader positions.
entrypoint: position_manager.py
methods:
  - name: position_manager
    args: []
    description: Iterate over open_positions.json, adjust stops/size/closures per rules, log actions, and return per-trade directives.
    returns: list of {token, action, reason}
---

# Position Manager

## Data Sources

- `/data/.openclaw/workspace/paper_trades/open_positions.json` – live trades (entry price, stop, TP, size, timestamps).
- `/data/.openclaw/workspace/paper_trades/trades_log.json` – receives closes triggered by this manager.
- `/data/.openclaw/workspace/paper_trades/position_actions.json` – append-only audit log of every action taken (HOLD/TRAIL_STOP/PARTIAL_CLOSE/CLOSE).

## Rules Implemented

1. **Partial take profit + trailing activation**
   - At `+4%`, sell 50% (marks `partial_50_hit`) and reset the stop to break-even.
   - At `+8%`, sell another 25%, arm the trailing stop, and follow price with a 3% gap.
2. **Trailing stop**
   - Once armed (after the +8% partial), keep `trail_high` updated and cut the reminder if price retraces >3% from the high.
3. **Loser control**
   - At `–3%`, exit immediately.
4. **Time decay**
   - If a trade has been open >2 hours **and** |pnl| < 1%, close it for lack of movement.

## Outputs & Side Effects

- Updates open positions in place (stop levels, position size, or removal if closed).
- Adds forced closes to `trades_log.json` with `exit_time`, `exit_price`, `exit_reason`.
- Appends action entries to `position_actions.json` with token, action, reason, pnl%, hours in trade.
- Returns a list like:
  ```json
  [
    {"token": "ETH", "action": "TRAIL_STOP", "reason": "Move stop to break-even"},
    {"token": "G", "action": "CLOSE", "reason": "Loser control triggered (-5.20%)"}
  ]
  ```

Run this skill periodically (e.g., via the autonomous loop) after price updates so open positions stay aligned with the playbook.
