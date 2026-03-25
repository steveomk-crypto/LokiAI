# Live Operating Mode

## Purpose
This document defines the current allowed operating mode of the LokiAI system.
It exists to keep the dashboard honest, streaming safe, outputs controlled, and external claims aligned with reality.

## Core operating truth
The system is currently in a:
- paper-only trading mode
- controlled automation mode
- Telegram outbound operator mode
- X draft-first public mode
- build-in-public operator/stream mode

This is not a live-money autonomous trading system at the current operating stage.

---

# 1. Trading Mode
## Current mode
Paper-only.

## Allowed
- scanner
- paper trader
- position manager
- flatten
- reports
- market summaries
- live Coinbase ingest for data visibility

## Not allowed
- autonomous live order execution
- implying real-money automation is active
- treating staged Coinbase funds as active system capital

## Public truth rule
Be explicit that real-money live execution is not currently active.

---

# 2. Automation Loop
## Current mode
Allowed.

The main automation loop may run, but only within the current paper-first operating constraints.

## Safe operator actions
- Start Automation
- Stop Automation
- Run Cycle
- Flatten V2
- Run Reports

## Rule
Automation running does not imply live-money automation.

---

# 3. Telegram Mode
## Current mode
Operator-channel outbound mode.

## Working
- Trading lane outbound
- Ops lane outbound
- Social lane outbound
- Comms outbound
- Web outbound
- lane routing and test sends

## Not fully working
- inbound Telegram Comms conversation loop

## Known issue
Telegram inbound via the OpenClaw Telegram provider is currently blocked by a provider/runtime startup failure.
This should be treated as a known issue and not represented as solved.

## Allowed
- Trading updates
- Ops alerts
- Social drafts
- test sends
- operator outbound messaging

## Not allowed / not reliable
- claiming Telegram inbound Comms is operational
- relying on Comms as a real inbound chat lane until provider issue is resolved

---

# 4. X Mode
## Current mode
Manual.

## Allowed
- generate drafts
- queue drafts
- inspect drafts
- prepare post targets
- inspect X subsystem state in dashboard

## Not allowed by default
- auto-posting publicly
- approval-less posting
- autonomous replies
- public arguments
- exaggerated performance claims

## Rule
X is manual for now. Drafts and queueing are allowed, but public posting should remain a deliberate operator action.

---

# 5. Dashboard Mode
## Current mode
Truth surface.

The dashboard should represent actual backend behavior, actual output state, and actual operational limitations.

## Rules
- no fake buttons
- no fake states
- no fake live-trading impression
- no pretending blocked/incomplete systems are fully working

## Safe to show
- operator rail
- outputs snapshot
- action feed
- top opportunities
- market summary
- cycle state

---

# 6. Stream Mode
## Current mode
Build-in-public operator view.

## The story
The system is being built and operated live as:
- scanner
- dashboard
- paper trader
- Telegram routing
- X drafting/output system
- future product/operator kit

## The story is not
- finished autonomous profit engine
- fully autonomous live-money system
- finished commercial product

## Preferred framing
The machine is being built in public.
The machine is the product.

---

# 7. Safe Click Policy
## Safe live clicks
- Start Automation
- Stop Automation
- Run Cycle
- Run Reports
- Flatten V2
- Telegram Test
- Telegram Social
- X Draft
- X Queue
- X Inspect
- output Inspect actions
- scanner Run

## Use with caution
- X Post
- anything that creates public-facing artifacts
- anything that could be mistaken for a live signal claim

## Not safe to imply
- Telegram Comms inbound works
- X is fully autonomous
- live money trading is active

---

# 8. Current Mode Summary
The current intended operating mode is:
- Trading: paper-only
- Automation: allowed
- Telegram: outbound operator mode
- X: draft_only
- Dashboard: truth surface
- Stream: build-in-public operator view

## Summary sentence
LokiAI is currently operating as a paper-first live operator stack with controlled automation, Telegram outbound routing, X draft-first public output, and a dashboard designed to reflect the system truthfully.
