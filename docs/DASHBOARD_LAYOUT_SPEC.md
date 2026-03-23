# Dashboard Layout Spec

## Goal
Translate the dashboard product spec into concrete screen structure so the rebuild has a clear visual and functional map.

This layout spec covers:
1. **Operator dashboard layout** (private)
2. **Stream dashboard layout** (public)

Both views should be fed from the same backend truth sources, but they should not expose the same level of detail.

---

# 1. Operator Dashboard Layout

## Design intent
- Truth-first
- Dense but readable
- Built for monitoring and debugging
- Not necessarily pretty before useful

## Suggested layout
### Top bar
Persistent slim header with:
- system mode (`rebuild`, `paper only`, `quality-only`, etc.)
- scanner status
- websocket status
- last global update timestamp
- stale-data warning indicator

### Main grid
Use a 3-column responsive grid.

## Row 1 — Health / high signal overview
### Panel A: System Health
Contents:
- scanner last run
- scanner signal count
- websocket connected/disconnected
- websocket last message time
- tracked Coinbase products
- dashboard data freshness
- daemon/loop status later

Purpose:
Immediate "is the machine alive?" answer.

### Panel B: Market State Summary
Contents:
- total signals this run
- high-quality signals
- avg top score
- breadth / positive ratio if available
- count of repeated/persistent names

Purpose:
Quick quality snapshot of the latest scanner state.

### Panel C: Alerts / Warnings
Contents:
- stale data warnings
- websocket disconnected
- scanner failed
- malformed files
- path/runtime issues
- service restart hints

Purpose:
No hunting. Problems should be obvious.

## Row 2 — Scanner intelligence
### Panel D: Top Scanner Opportunities
Contents:
- top ranked names
- score
- momentum
- persistence
- trend label
- venue/actionability tag later (`coinbase-actionable`, `dex-context`, etc.)

Purpose:
Main scanner output in one place.

### Panel E: Persistence / Repeat Names
Contents:
- names showing up repeatedly
- persistence count
- strengthening vs weakening marker
- maybe simple sparkline later

Purpose:
Highlight what is actually surviving multiple scans.

### Panel F: Scanner Run History
Contents:
- recent run timestamps
- signal count per run
- high-quality count per run
- compact mini-chart later

Purpose:
Understand cadence and whether quality is improving or degrading.

## Row 3 — Coinbase live layer
### Panel G: Coinbase Live Movers
Contents:
- top live movers from websocket cache
- 1m / 5m / 15m drift
- freshness seconds
- last price

Purpose:
Live pulse view separate from scanner snapshots.

### Panel H: Coinbase Universe Health
Contents:
- tracked product count
- active product count
- stale symbols count
- most recently updated symbols
- reconnect count

Purpose:
Know whether the websocket layer is actually healthy.

### Panel I: Websocket Activity History
Contents:
- recent snapshot timestamps
- message count growth
- connection uptime/reconnects
- later simple chart of update activity

Purpose:
Catch silent data death early.

## Row 4 — Command bay + later expansion
### Panel J: Command / Controls Bay (placeholder initially)
Contents:
- disabled control groups for scanner, websocket, dashboard, loop, trader, alerts, reports
- labeled buttons/toggles in locked state
- system status lights / readiness markers
- clear operator-only treatment

Purpose:
Reserve a real cockpit control zone now so the operator view can grow into functional controls later without redesigning the whole layout.

### Future Panel K: Paper Trader Summary
- open positions
- realized/unrealized PnL
- trade count
- win rate

### Future Panel L: Risk / Position Actions
- stops moved
- closes
- position manager actions

### Future Panel M: Product / Content Output Queue
- latest Substack draft
- latest Gumroad pack
- Telegram/X output readiness

---

# 2. Stream Dashboard Layout

## Design intent
- readable instantly
- visually stable for 24/7 streaming
- motion without chaos
- informative without being cluttered
- conversion-oriented

## Suggested layout
Use a widescreen layout suitable for YouTube streaming.

## Top banner
Large branded strip with:
- `LokiAI Market Engine`
- current mode (`rebuild`, `paper only`, `scanner live`, etc.)
- scanner status
- websocket status
- timestamp / timezone

Purpose:
A viewer should instantly know the system is live.

## Main body
Two-column main layout with a bottom CTA/footer band.

## Left column — live market intelligence
### Panel A: Live Coinbase Pulse
Contents:
- top live movers
- price
- short-term drift
- freshness indicator

Purpose:
Immediate motion. Makes the stream feel alive.

### Panel B: Scanner Highlights
Contents:
- latest top scanner names
- score / persistence / trend
- maybe label: `watch`, `building`, `hot`, `fading`

Purpose:
Show the system is doing structured analysis, not just showing random tickers.

### Panel C: System Progress
Contents:
- scans completed today
- signals logged today
- websocket tracked products
- rebuild progress / current phase

Purpose:
Narrative of progress and operational seriousness.

## Right column — trust + conversion
### Panel D: Performance / Operating Status
For now show:
- paper-only mode
- no live trading yet
- funded Coinbase account staged but inactive until stability
- honest system-status notes

Later show:
- paper PnL
- trade count
- win rate
- drawdown discipline

Purpose:
Build trust through transparency.

### Panel E: Latest Intelligence / Content
Contents:
- latest Atlas Pulse headline
- short summary snippet
- latest report/post title
- latest product mention

Purpose:
Turn the stream into a live intelligence channel.

### Panel F: Links / Support / CTA
Contents:
- Substack
- Gumroad
- Telegram / community route later
- support/tips route later
- QR codes later if useful

Purpose:
This is the monetization bridge.

## Bottom band / ticker
Rotating footer bar with:
- short scanner notes
- system messages like `scanner live`, `paper only`, `quality gate active`
- product/newsletter prompts

Purpose:
Keep the screen feeling active even during quiet periods.

---

# 3. Shared design rules

## Rule: no clutter
Every panel must justify its existence.

## Rule: stale state is better than broken UI
If a data source stops updating, show:
- stale badge
- last update time
instead of hiding the panel or crashing.

## Rule: public view is curated
Public view should never expose:
- raw logs
- controls
- secrets
- sensitive financial/account details
- private debugging internals

## Rule: operator view gets the truth
Even if ugly.

## Rule: stream view gets the story
But the story must be honest.

---

# 4. Implementation order
## First build
- top bar / health state
- scanner highlights
- websocket pulse
- market state summary

## Second build
- operator diagnostics and history panels
- stream CTA and latest intelligence sections

## Third build
- performance and trader sections after data is trustworthy

---

# 5. Immediate use
This spec should guide the rebuild instead of trying to salvage the old panel layout.
