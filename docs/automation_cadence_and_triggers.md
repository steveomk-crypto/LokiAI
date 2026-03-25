# Automation Cadence and Trigger Rules

## Purpose
This document defines the intended cadence and trigger model for the LokiAI system.
It separates the fast internal engine from the slower human/public output layers.

---

# 1. Architecture Overview
The system should operate in layers:

## Layer A — Core Engine
Fast loop for market sensing and paper execution.

## Layer B — Telegram
Event-driven notifications plus scheduled summaries.

## Layer C — X
Selective, slower, and editorial/public-facing.

## Layer D — Reports / Analytics
Slower reflective outputs and supporting artifacts.

---

# 2. Core Engine

## Purpose
Keep the machine responsive to market conditions and position state.

## Intended cadence
- target: every 30 seconds
- acceptable fallback: every 60 seconds if needed for stability

## Tasks in order
1. market_scanner
2. paper_trader
3. position_manager

## Rules
- scanner should run first each cycle
- paper trader should consume the most recent scanner state
- position manager should run after paper trader each cycle
- if there is nothing to do, components should no-op cleanly
- the core engine should not wait on human-facing output layers

## Goal
Fast sensing, fast paper-trading response, fast position management.

---

# 3. Telegram

## Purpose
Provide operator awareness through both immediate event messages and structured summaries.

## Telegram behavior splits into two streams

### A. Immediate event notifications
These should send as events happen.

#### Send immediately for
- new position opened
- position closed
- flatten completed
- stop loss / take profit / time stop event
- risk gate change
- meaningful PnL change
- major automation failure or incident (to Ops lane)

#### PnL event rule
Do not send for tiny noise.
Send when:
- realized PnL changes
- unrealized PnL changes materially
- position-level PnL crosses a meaningful threshold

### B. Scheduled Trading summary
#### Intended cadence
- every 15 minutes

#### Summary contents
- current mode/status
- open positions
- realized PnL
- unrealized PnL
- notable signals
- risk posture
- important recent changes

## Lane usage
- Trading lane = trading events + 15-minute trading summaries
- Ops lane = runtime/incident/health alerts
- Social lane = draft copy for public surfaces
- Comms lane = human/agent coordination only
- Web lane = infra/deploy notes only

## Telegram rules
- event notifications should be concise
- summaries should be compact and structured
- avoid duplicate/no-change spam
- Trading lane should not become a general-purpose log sink

---

# 4. X

## Purpose
Serve as the public-facing editorial/output layer.
It should be selective, useful, and non-spammy.

## Cadence model
- event-driven
- capped frequency
- not tied to the fast core engine cadence

## Frequency rule
- no per-cycle posting
- no posting for every trade or minor PnL change
- target scarcity over activity

## Suggested cap
- no more than 1 post every 2–4 hours unless a clearly important event justifies it

## Good X triggers
- meaningful market regime shift
- notably strong radar state
- important system milestone / build progress
- selective receipt/result moment
- product/system evolution update

## Bad X triggers
- every scanner cycle
- every small trade event
- every PnL move
- repetitive internal summaries
- emotionally reactive posting

## X rule
X should be manual for now, selective, and draft-first.
It is not a mirror of Telegram or internal events.

---

# 5. Reports / Analytics

## Purpose
Generate slower reflective outputs and performance artifacts.

## Intended cadence
- every 15 to 30 minutes
- or manual only during rebuild/testing phases

## Tasks
- performance analyzer
- heavier report generation
- lower-priority supporting analytics

## Rule
These should not sit inside the fast 30-second core loop.

---

# 6. Recommended Final Split

## Fast loop (30s target)
- market_scanner
- paper_trader
- position_manager

## Telegram event layer
- event-driven
- immediate for position/risk/PnL changes

## Telegram summary layer
- every 15 minutes

## X layer
- selective, event-driven, capped

## Reports layer
- every 15–30 minutes or manual

---

# 7. Design Principles
- fast internal engine
- calm external outputs
- operator-aware notifications
- public scarcity over spam
- event-driven when possible
- summary-driven when useful

---

# Summary
The system should not run every human-facing output on the same clock as the core engine.
The core engine should be fast.
Telegram should combine immediate event notifications with 15-minute summaries.
X should be selective and capped.
Reports should be slower.
