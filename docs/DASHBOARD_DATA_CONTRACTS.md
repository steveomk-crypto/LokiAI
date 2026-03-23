# Dashboard Data Contracts

## Purpose
Define exactly which data sources feed the rebuilt dashboard and what fields each panel should expect.

The goal is to keep the dashboard rebuild clean:
- backend truth sources are explicit
- panel dependencies are explicit
- stale/missing data can be handled intentionally
- operator and stream views can share the same underlying contracts

## Core rule
The dashboard reads file-based state/cache first. It should not depend on live model calls to render.

---

# 1. Truth sources currently available

## Scanner outputs
### File: `market_logs/YYYY-MM-DD.jsonl`
Status: **available now**
Producer: `autonomous_market_loop.py --task market_scanner`

### Typical fields per line
- `timestamp`
- `token`
- `volume`
- `momentum`
- `status`
- `persistence`
- `liquidity_change_ratio`
- `volume_acceleration_ratio`
- `buy_pressure_proxy`
- `liquidity_health`
- `momentum_5m`
- `momentum_15m`
- `momentum_60m`
- `momentum_alignment_score`
- `momentum_trend`
- `momentum_score`
- `volume_score`
- `persistence_score`
- `liquidity_score`
- `alignment_score`
- `score`

### File: `cache/market_state.json`
Status: **available now**
Producer: scanner loop

### Expected fields
- `mode`
- `computed_at`
- `metrics.avg_top_score`
- `metrics.high_quality_signals`
- `metrics.breadth_positive`
- `metrics.total_signals`
- `top_opportunities[]`
  - `token`
  - `score`
  - `momentum`
  - `volume`
  - `persistence`
  - `status`
  - `trend`

### File: `market_scanner/candidates.json`
Status: **available but may be empty**
Producer: DEX candidate scanner / market scanner sidecar

### Expected fields
Current shape may vary. Treat as optional until stabilized.

---

## Coinbase websocket outputs
### File: `cache/coinbase_ws_state.json`
Status: **available now**
Producer: `feeds/coinbase_ws.py`

### Expected fields
- `status`
- `connected`
- `started_at`
- `last_message_at`
- `last_flush_at`
- `tracked_products`
- `messages_received`
- `reconnect_count`
- optional `last_error`

### File: `cache/coinbase_products.json`
Status: **available now**
Producer: `feeds/coinbase_ws.py`

### Expected fields per product
- `product_id`
- `base_currency`
- `quote_currency`
- `status`
- `base_increment`
- `quote_increment`
- `min_market_funds`
- `auction_mode`
- `preferred`

### File: `cache/coinbase_tickers.json`
Status: **available now**
Producer: `feeds/coinbase_ws.py`

### Expected fields per product id
- `product_id`
- `base_currency`
- `quote_currency`
- `status`
- `price`
- `volume_24h`
- `best_bid`
- `best_ask`
- `last_update`
- `sequence`
- `drift_60s`
- `drift_300s`
- `drift_900s`
- `freshness_seconds`

### File: `market_logs/coinbase_ws/YYYY-MM-DD.jsonl`
Status: **available now**
Producer: `feeds/coinbase_ws.py`

### Expected fields per snapshot
- `timestamp`
- `connected`
- `messages_received`
- `tracked_products`
- `top_movers[]`

---

## System/service outputs
### File: `system_logs/coinbase_ws.pid`
Status: **available now**
### File: `system_logs/coinbase_ws.log`
Status: **available now**
### File: `system_logs/dashboard_ui.pid`
Status: available if dashboard launched
### File: `system_logs/dashboard_ui.log`
Status: available if dashboard launched

These should feed diagnostics and service-state helpers, not public panels directly.

---

# 2. Operator dashboard panel contracts

## Panel: System Health
### Required sources
- `cache/market_state.json`
- `cache/coinbase_ws_state.json`
- optional PID/log checks

### Required display fields
- scanner last run: `market_state.computed_at`
- total signals: `metrics.total_signals`
- websocket connected: `coinbase_ws_state.connected`
- websocket last message: `coinbase_ws_state.last_message_at`
- tracked products: `coinbase_ws_state.tracked_products`
- reconnect count: `coinbase_ws_state.reconnect_count`

### Stale logic
Show warning if:
- scanner timestamp too old
- websocket last message too old
- state file missing

## Panel: Market State Summary
### Required source
- `cache/market_state.json`

### Fields
- `metrics.avg_top_score`
- `metrics.high_quality_signals`
- `metrics.breadth_positive`
- `metrics.total_signals`
- `top_opportunities[0:3]`

## Panel: Alerts / Warnings
### Required sources
- missing/stale checks across all primary files
- optional service logs/pids

### Fields / triggers
- scanner stale
- websocket stale/disconnected
- candidates file missing or empty
- malformed JSON
- dashboard missing its own inputs

## Panel: Top Scanner Opportunities
### Required source
- `cache/market_state.json`
- optional deeper enrichment from latest `market_logs/YYYY-MM-DD.jsonl`

### Fields
- token
- score
- momentum
- volume
- persistence
- status
- trend

## Panel: Persistence / Repeat Names
### Required source
- recent lines from `market_logs/YYYY-MM-DD.jsonl`

### Derived fields
- token repeat count over recent runs
- max persistence
- latest trend
- strengthening / weakening heuristic later

## Panel: Scanner Run History
### Required source
- recent lines from `market_logs/YYYY-MM-DD.jsonl`

### Derived fields
- runs grouped by timestamp
- signal count per run
- top score per run
- high-quality count heuristic later

## Panel: Coinbase Live Movers
### Required source
- `cache/coinbase_tickers.json`

### Fields
- product_id
- price
- drift_60s
- drift_300s
- drift_900s
- freshness_seconds
- volume_24h

### Sort suggestion
Sort by absolute `drift_300s` or freshness-weighted short-horizon movement.

## Panel: Coinbase Universe Health
### Required sources
- `cache/coinbase_ws_state.json`
- `cache/coinbase_products.json`
- `cache/coinbase_tickers.json`

### Derived fields
- tracked products count
- products with live price
- stale product count
- freshest symbols
- reconnect count

## Panel: Websocket Activity History
### Required source
- `market_logs/coinbase_ws/YYYY-MM-DD.jsonl`

### Derived fields
- snapshot timestamps
- messages_received progression
- connected state over time
- top mover snapshots

## Panel: Command / Controls Bay (placeholder phase)
### Required source
None required for v1 placeholder mode.

### Initial fields
Static/operator-configured display only:
- control group label
- control name
- state: `locked`, `offline`, `pending`, or `ready later`
- optional status light color

### Future sources
Once controls are real, this panel can read service state and readiness from:
- `cache/coinbase_ws_state.json`
- scanner freshness / state files
- future loop/trader service state files

### Rule
This panel is operator-only. It must not appear as a functional control surface on the public stream dashboard.

---

# 3. Stream dashboard panel contracts

## Panel: Live Status Banner
### Required sources
- `cache/market_state.json`
- `cache/coinbase_ws_state.json`

### Fields
- scanner active (derived from market_state freshness)
- websocket active (`connected` + freshness)
- current mode (manual config/string for now)
- current timestamp

## Panel: Live Coinbase Pulse
### Required source
- `cache/coinbase_tickers.json`

### Fields
- top movers by short-horizon drift
- price
- movement
- freshness

## Panel: Scanner Highlights
### Required source
- `cache/market_state.json`

### Fields
- top opportunities
- score
- persistence
- trend

## Panel: System Progress
### Required sources
- `cache/market_state.json`
- `cache/coinbase_ws_state.json`
- scanner log files for counts if needed

### Fields
- scans completed today (derived)
- signals logged today (derived)
- tracked Coinbase products
- current operating mode text

## Panel: Performance / Operating Status
### Immediate mode
Use manually controlled text plus paper-only notice.

### Later required sources
- `paper_trades/trades_log.json`
- `paper_trades/open_positions.json`
- `performance_reports/...`

## Panel: Latest Intelligence / Content
### Immediate mode
Can be fed manually or from docs/artifacts.

### Likely sources later
- latest Substack metadata/doc
- latest Gumroad pack metadata
- latest report file

## Panel: Links / Support / CTA
### Source
Static config or dashboard constants for now

### Fields
- Substack URL
- Gumroad URL
- Telegram/community URL later
- support/tip link later

---

# 4. Missing contracts / future sources
These are not yet stable enough but likely needed later.

## Paper trader contracts
Potential sources:
- `paper_trades/open_positions.json`
- `paper_trades/trades_log.json`
- `paper_trades/position_actions.json`

## Risk contracts
Potential sources:
- `risk_logs/risk_decisions.json`

## Performance contracts
Potential sources:
- `performance_reports/`
- `trade_journal/performance_report.json`

## Content/product contracts
Potential sources:
- `docs/gumroad/...`
- `artifacts/gumroad/...`
- Substack output metadata later

---

# 5. Build guidance
## First dashboard build should depend only on:
- `cache/market_state.json`
- `market_logs/YYYY-MM-DD.jsonl`
- `cache/coinbase_ws_state.json`
- `cache/coinbase_products.json`
- `cache/coinbase_tickers.json`
- `market_logs/coinbase_ws/YYYY-MM-DD.jsonl`

That is enough to rebuild a useful first version.

## Rendering rule
If a required file is missing:
- show `missing`
- show `stale`
- show last known timestamp if possible
- do not crash the whole UI

## Final rule
The dashboard should treat missing data as an operational condition, not an exception path.
