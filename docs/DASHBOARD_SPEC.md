# Dashboard Spec

## Purpose
The dashboard should be rebuilt from scratch as a deliberate product, not treated as a patched-together leftover UI. It has two related but distinct jobs:
1. **Operator dashboard** for internal control, monitoring, and debugging
2. **Stream dashboard** for public-facing visibility, credibility, and revenue conversion

The old dashboard should not dictate the new design. This spec defines the new intent first.

## Core Principle
One backend truth source. Two views.
- **Private operator view** for real system management
- **Public stream view** for 24/7 display and audience growth

The public view must never be the control surface.

## Why Rebuild
The previous dashboard existed before the current strategic framing was fully clear. The new system is not just a trader panel. It is part trading machine, part intelligence surface, part content/revenue funnel. Rebuilding from spec is cleaner than inheriting old assumptions.

## Dashboard Goals
### Operator dashboard goals
- show real system health
- show scanner backlog quality
- show websocket/live ingest health
- show trader state later
- support debugging and decision-making
- expose enough internal truth to fix problems fast

### Stream dashboard goals
- make the system legible to an audience in seconds
- prove the machine is live and doing real work
- create watchability for 24/7 streaming
- build trust through visible process and honest reporting
- route attention toward Substack, Gumroad, Telegram, tips, and future paid products

## Architecture
### Backend
Single backend / data layer fed by:
- scanner logs and state
- Coinbase websocket cache/state
- paper trading state and performance (later)
- market summaries and reports

### Frontend views
#### 1. Operator view (private)
Internal-only. Detailed. Truth-first.

#### 2. Stream view (public)
Curated subset of data. Visually stable. Readable. Safe for YouTube.

## Operator Dashboard Spec
### Must-have panels
#### System health
- scanner status
- scanner last run timestamp
- websocket connection status
- websocket last update
- tracked product count
- file freshness / stale data warnings
- daemon/loop status if applicable later

#### Command / Controls Bay (placeholder first)
- dedicated operator-only control surface zone
- visible from day one, but disabled until systems are safely wired
- placeholder controls for scanner, websocket, dashboard, loop, trader, alerts, reports
- status lights / locked indicators to preserve the cockpit metaphor without exposing unsafe functionality yet

#### Scanner backlog
- latest scan summary
- top ranked opportunities
- persistence counts
- recent repeat names
- trend classifications
- signal count over time

#### Coinbase live pulse
- top live movers from websocket cache
- freshness timestamps
- short-horizon drift metrics
- tracked universe summary

#### Market state
- avg top score
- high-quality signal count
- total signals
- breadth / health metrics if useful

#### Diagnostics
- parser/runtime errors
- stale file warnings
- service down indicators
- recovery guidance / flags

### Future operator panels
- paper-trader open/closed trades
- position lifecycle panel
- risk state and alerts
- performance report summaries
- content/product pipeline status

## Stream Dashboard Spec
### Public design goals
- legible in 3 seconds
- looks alive 24/7
- no clutter
- no secret/sensitive data
- no fragile internal controls
- no embarrassing debug noise

### Must-have public panels
#### Live status banner
- system online/offline
- scanner active
- websocket active
- current mode: paper / quality-only / rebuild / etc.

#### Market pulse
- top live Coinbase movers from tracked universe
- recent scanner highlights
- rotating signal summary cards

#### Progress / credibility panel
- scans completed today
- signals captured today
- days running / uptime metrics
- paper-trading mode notice
- honest note that live funds are staged but inactive until stable

#### Performance panel (later when ready)
- paper PnL
- win rate
- trade count
- drawdown control summary
- only once those numbers are stable and credible

#### Content / product CTA panel
- Substack URL
- Gumroad URL
- Telegram/community/tips route
- branded QR or rotating link area later

#### Recent intelligence panel
- latest Atlas Pulse / market brief headline
- recent scanner narrative snippets
- next product/report teaser

### Optional stream features later
- rotating market commentary ticker
- "top watchlist" carousel
- AI operator notes panel
- countdowns to next scanner batch/report
- supporter / tip acknowledgements if added later

## Public Safety Rules
The stream dashboard must never expose:
- API keys / secrets
- private account controls
- raw logs with sensitive content
- email/account identifiers beyond intentional public branding
- wallet/account balances unless explicitly intended
- anything that could enable abuse or compromise
- real-money execution controls

## Revenue Role
The stream dashboard is a conversion surface, not just a status screen.
Its job is to convert attention into:
- newsletter readers
- Gumroad buyers
- tips/support
- future subscribers/community members
- long-term trust in the system

## Brand Requirements
The dashboard should match the brand voice:
- sharp
- calm
- data-driven
- no hype
- no scam energy
- no fake urgency
- professional operator aesthetic

The visual experience should feel like an active intelligence machine, not a meme casino.

## Technical Requirements
- stable enough for long-duration display
- resilient to partial data outages
- able to show stale-state warnings instead of breaking
- read from file-based state/cache first
- avoid unnecessary model/API dependency for rendering
- designed so operator and stream views can evolve independently

## Build Order
### Phase 1
Define backend truth sources and data contracts:
- scanner outputs
- websocket outputs
- market state summaries

### Phase 2
Rebuild operator dashboard first:
- truth-first
- useful immediately
- enough to inspect scanner/websocket quality

### Phase 3
Create separate stream view:
- simplified
- safer
- branded
- conversion-aware

### Phase 4
Add paper-trading/performance surfaces once data is trustworthy

### Phase 5
Refine public UX for 24/7 stream quality and monetization

## Immediate Rule
Do not inherit the old dashboard structure blindly. Start from the current machine goals and build the UI that serves them.
