# Coinbase Websocket Service Spec

## Purpose
The Coinbase websocket layer is the live-ingest component of the trading machine. It should provide fast market-state updates that complement the slower scanner snapshot cycle. The websocket service is not the decision engine. It is the real-time input layer that feeds scanner context, dashboard freshness, and eventual execution awareness.

## Role In The Stack
### Websocket service
- Maintains live Coinbase market awareness
- Streams fast updates from Coinbase
- Writes normalized state/cache files for downstream consumers
- Runs continuously as a separate process

### Scanner
- Runs on a slower interval
- Reads websocket-produced state/cache plus broader market data
- Produces ranked opportunity outputs and persistence history

### Dashboard / trader / alerts
- Read structured outputs and/or summarized live state
- Should not depend directly on raw websocket message noise

## Core Principle
Separate ingest from judgment.
- **Websocket = pulse**
- **Scanner = judgment**

Keeping them separate improves reliability, debugging, and system clarity.

## Why This Exists
Without a websocket layer, the system only sees the market at snapshot intervals. That is enough for baseline scanning but weak for:
- intraday acceleration detection
- freshness on the dashboard
- detecting when a move is beginning vs already gone
- future execution support

## Initial Scope
This service should focus on Coinbase spot market data relevant to the current system goals.

### Primary goals
1. Maintain a live view of Coinbase-listed market activity
2. Feed scanner context for tiny-account tradability and momentum quality
3. Improve dashboard freshness
4. Create a foundation for eventual live-trading support without enabling live trading yet

## Non-Goals For Now
- no real-money execution
- no automatic order placement
- no complex orderbook analytics unless needed later
- no overbuilt infra before core stability is achieved

## Proposed Inputs
The exact Coinbase websocket channels can be finalized later, but the initial design should support data such as:
- ticker / best bid-ask / price updates
- trades / last trade flow
- product-level status if available
- optional orderbook summary later if justified

## Universe Focus
The websocket service should prioritize:
- Coinbase-listed spot products
- USD / USDC / USDT-accessible pairs where relevant
- names the scanner or account can actually use

This service should not waste attention on irrelevant pairs if they do not support the scanner doctrine.

## Output Files / State
The websocket service should write local cache/state under the workspace, for example:
- `cache/coinbase_ws_state.json`
- `cache/coinbase_products.json`
- `cache/coinbase_tickers.json`
- `cache/coinbase_recent_trades.json`
- optional rolling snapshots under `market_logs/coinbase_ws/`

The exact schema can evolve, but the key requirement is that downstream consumers can read stable files.

## Recommended Cached Views
### 1. Product universe
A normalized list of Coinbase tradeable products with:
- symbol/product id
- base/quote
- status/tradability flags
- product type / venue notes if needed

### 2. Live ticker state
Per product:
- last price
- 24h change if available
- volume if available
- timestamp of most recent update

### 3. Short-horizon movement state
Per product, lightweight derived fields such as:
- 1m / 5m / 15m drift
- update recency
- simple acceleration flags
- recent trade count / pulse if easy to compute

### 4. Scanner handoff state
A simplified feed optimized for the scanner, e.g.:
- Coinbase-listed boolean
- freshness score
- recent movement score
- recent activity score
- tradability flags

## Process Model
The websocket service should run as a **separate always-on process** from:
- scanner runs
- dashboard process
- paper trader
- daemon loop

This separation allows:
- independent restarts
- clearer logs
- cleaner fault isolation
- dashboard use without forcing scanner execution

## Logging
The service should maintain its own logs, for example:
- `system_logs/coinbase_ws.log`
- `system_logs/coinbase_ws.pid`

If it disconnects or falls behind, that should be visible without guessing.

## Reliability Requirements
The websocket layer should include:
- reconnect handling
- heartbeat / liveness awareness
- safe cache writes
- tolerance for temporary API/network failures
- no crash cascade into scanner/dashboard/trader

## Scanner Integration
Scanner V2 should use websocket outputs to improve ranking for Coinbase-actionable setups.

Examples:
- boost names with fresh live activity and clean movement
- penalize stale names with weak live confirmation
- improve trend freshness for small-account opportunity selection
- separate currently active names from static 24h gainers

## Dashboard Integration
The dashboard should eventually use websocket state for:
- live market freshness indicator
- current active movers panel
- Coinbase-watchlist pulse
- data freshness / last-update timestamp

## Trader Integration
Not for live deployment yet. But eventually the trader can use websocket-derived state for:
- confirming momentum freshness
- monitoring live position context
- improving exit awareness

For now, trader use should remain paper-only.

## Implementation Plan
### Phase 1
- Build minimal Coinbase websocket client/service
- Subscribe to a constrained useful product set
- Write cache/state files
- Add logs and PID handling

### Phase 2
- Feed scanner with websocket freshness fields
- Add dashboard panels showing websocket health and live movers

### Phase 3
- Tune product universe and derived metrics
- Improve reconnection and cache durability

### Phase 4
- Optional future trader integration for paper/live-readiness only

## Safety / Control Rule
The websocket service is an input source only. It must not place trades or trigger public actions on its own.

## Working Rule
If the websocket is down, the scanner can still run. If the scanner is down, the websocket can still maintain state. Separation is the feature.
