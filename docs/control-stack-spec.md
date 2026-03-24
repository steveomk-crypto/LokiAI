# Control Stack Spec

Updated: 2026-03-24

## Purpose

This document defines the intended architecture, control model, runtime dependencies, and dashboard truth model for the local trading/operator stack.

The goal is to make the system:
- understandable
- operable from the dashboard
- replayable/tunable from stored logs
- compatible with a local-first assistant workflow using Ollama/OpenClaw

This spec exists to stop the system from drifting into a pile of scripts with conflicting UI semantics.

---

## Goals

1. **Single operator truth** — operator dashboard and stream dashboard should reflect the same runtime reality.
2. **Correct dependency ordering** — downstream components should not appear healthy when upstream data plane is stale/broken.
3. **Explicit control semantics** — persistent services, one-shot jobs, and mode toggles must not be conflated.
4. **Replay-grade logging** — strategy tuning should be based on decision-grade data, not vibes.
5. **Local-first control + assistant** — low-complexity assistant work should run local-first, while deterministic control actions remain script-driven.

---

## System Topology

The stack has four layers.

### 1. Data Plane
Required before trading logic is meaningful.

#### Coinbase Feed / Websocket
Purpose:
- maintain live market connectivity
- provide product state, price, freshness, and drift

Primary outputs:
- `cache/coinbase_ws_state.json`
- `cache/coinbase_tickers.json`

#### Market Scanner
Purpose:
- rank tradable opportunities
- produce the shortlist for paper trader / downstream decisions

Primary outputs:
- `cache/market_state.json`

---

### 2. Trading Plane
Consumes the data plane.

#### Paper Trader V2
Purpose:
- select, open, manage, and close V2 paper positions

Primary outputs:
- `paper_trades/open_positions_v2.json`
- `paper_trades/trades_log_v2.json`
- `paper_trades/paper_trader_v2_state.json`
- `paper_trades/paper_trader_v2_audit_summary.json`

Replay-grade outputs:
- `paper_trades/paper_trader_v2_decisions.jsonl`
- `paper_trades/v2_candidate_evaluations.jsonl`
- `paper_trades/v2_position_snapshots.jsonl`
- `paper_trades/v2_exit_events.jsonl`

#### Position Manager
Purpose:
- apply follow-up lifecycle / trade management rules to open positions

---

### 3. Orchestration Plane
Coordinates repeated execution.

#### Main Loop Daemon
Purpose:
- repeatedly invoke the market cycle
- function as scheduler / repeated executor, not a trading logic component itself

Important:
- daemon/process residency is not the same thing as recent successful cycle activity
- dashboard must expose both concepts separately

#### One-Shot Jobs
Examples:
- scanner run
- trader run
- flatten run
- report run
- market cycle run

These are jobs, not persistent services.

---

### 4. Output Plane
Downstream / reporting layer.

Components:
- market broadcaster
- telegram sender
- x autoposter
- performance analyzer
- sol shadow logger / sidecars

These should never be allowed to imply the trading core is healthy if the data plane is stale.

---

## Runtime Dependency Order

This is the required logical order.

### Tier 1 — Data Plane
1. Coinbase feed / websocket
2. market scanner

### Tier 2 — Trading Plane
3. paper trader V2
4. position manager

### Tier 3 — Orchestration
5. main loop daemon

### Tier 4 — Outputs
6. broadcaster
7. telegram sender
8. x autoposter
9. performance analyzer
10. sol shadow/logger sidecars

### Dependency Rules
- Trader health requires fresh scanner state and fresh websocket state.
- Scanner health requires fresh market/feed state.
- Output components may be functional while the trading plane is degraded, but should not imply core health.
- Main loop health must distinguish between **daemon resident** and **recent successful cycle**.

---

## Component Types

Each controlled unit must be classified as exactly one of the following.

### A. Persistent Service
Examples:
- Coinbase feed
- operator dashboard
- stream dashboard
- main loop daemon

Allowed controls:
- start
- stop
- restart

Observed state examples:
- running
- stopped
- degraded

### B. One-Shot Job
Examples:
- run scanner now
- run trader now
- flatten now
- run reports now
- run market cycle now

Allowed controls:
- run now

Observed state examples:
- idle
- running
- recently completed
- failed

### C. Mode Toggle / Policy Control
Examples:
- auto loop enabled
- broadcaster enabled
- x posting enabled
- paper-only mode
- local-model mode

Allowed controls:
- enable
- disable
- set mode

Observed state examples:
- enabled
- disabled
- mismatched

---

## Dashboard Truth Model

The dashboards must not rely on PID presence alone.

For each component, observed state should be derived from:
1. process presence (if relevant)
2. recent log activity
3. freshness of output/cache files
4. domain-specific truth

### Examples

#### Coinbase Feed
Healthy when:
- websocket says connected
- last message is recent
- ticker data is fresh

It should not show as dead purely because a PID probe is missing or stale.

#### Scanner
Healthy when:
- market_state is fresh
- scanner output is recent

It is a one-shot job; “recently completed” may be more truthful than “stopped.”

#### Main Loop
Expose both:
- **daemon resident** (process alive now)
- **recent cycle activity** (cycle start/end/task progress recent)

Top-level operator pill should collapse to something human-readable:
- RUNNING — daemon resident
- ACTIVE — recent cycle completed / recent loop activity
- IDLE — neither of the above

---

## Required Card Fields

Every operator dashboard component card should include:

1. **Name**
2. **Component type**
3. **Observed state**
4. **Desired state**
5. **Last successful action/run**
6. **Last error**
7. **Dependency health**
8. **Relevant controls**
9. **Last action result**

Without these, the UI becomes misleading under partial failure.

---

## Dashboard Layout Recommendation

### Operator Dashboard Sections

#### Data Plane
- Coinbase feed
- market scanner
- market state freshness

#### Trading Plane
- paper trader V2
- open slots
- latest trade action
- position manager

#### Orchestration
- main loop
- last cycle start/end
- task completion summary
- next cycle / sleep state if available

#### Outputs
- broadcaster
- telegram sender
- x autoposter
- reports
- shadow logger

### Stream Dashboard
Purpose:
- condensed status surface
- should consume the same runtime truth model as the operator dashboard
- must never invent a second independent interpretation of component health

---

## Control Model Recommendation

All actions should flow through a unified control adapter.

### Persistent Services
- `start_component(id)`
- `stop_component(id)`
- `restart_component(id)`

### One-Shot Jobs
- `run_job(id)`

### Mode / Policy Controls
- `set_mode(id, value)`

### Destructive Actions
- `flatten_positions(scope='v2')`

### Control Requirements
Every action should record:
- timestamp
- component id
- requested action
- shell/runner target
- success/failure
- human-readable message

This action result should feed directly into the operator dashboard card state.

---

## Component Registry Recommendation

The system should move toward a single registry/manifest describing all components.

Each component definition should include:
- id
- display name
- component type
- category/section
- command(s)
- pid file (if any)
- log path(s)
- primary output/cache files
- dependencies
- health derivation strategy
- destructive/safe flag

Both dashboards should render from this same registry.

This is the preferred path to reducing drift between operator/stream views.

---

## Main Loop Semantics

Main loop semantics caused recurring confusion and must be explicit.

### Distinguish:
- **Main loop daemon resident** — is the background loop process alive now?
- **Main loop recent activity** — did a market cycle run recently?
- **Main loop success/failure** — did the most recent cycle complete cleanly?

### Top-level display should prioritize operator meaning, not raw process trivia.

Recommended display states:
- `RUNNING` — daemon is resident and active
- `ACTIVE` — recent cycle completed or loop log is fresh
- `IDLE` — no daemon + no recent cycle
- `FAILED` — recent cycle attempted but failed

Detailed rows may still show daemon residency separately.

---

## Replay and Tuning Requirements

The trader must collect decision-grade telemetry to support historical evaluation.

### Required logs

#### Candidate evaluations
One row per candidate considered per cycle.

Fields:
- timestamp
- token / product id
- score
- momentum
- persistence
- trend/status
- price
- drift_300s
- freshness_seconds
- decision
- reason
- candidate tier if accepted

#### Position snapshots
One row per open position per cycle.

Fields:
- timestamp
- token / product id
- trade state
- move character
- entry/current price
- pnl
- highest pnl
- time in trade
- scanner score
- momentum
- persistence
- websocket drift/freshness
- trim/trail state
- remaining size

#### Exit events
One row per close/trim/de-risk action.

Fields:
- timestamp
- token / product id
- entry time
- time in trade
- pnl
- highest pnl
- drift/freshness
- move character
- thresholds in force
- exact exit reason/category

These logs are required for future replay quality.

---

## Local-First Assistant Control Model

The assistant should be local-first for low-complexity work.

### Desired behavior
- Ollama/local model handles cheap routine work
- higher-cost hosted models only used when needed
- deterministic system controls remain script/tool-driven

### Important principle
The dashboard/control plane should **not** depend on LLM reasoning to function correctly.

The assistant’s role is to:
- inspect
- summarize
- explain
- recommend
- trigger deterministic controls

The assistant should not be the sole source of runtime truth.

---

## Short-Term Implementation Priorities

### Priority 1 — Trustworthy operator model
- unify status derivation
- separate one-shot vs persistent semantics
- show dependencies and last success/error
- ensure operator + stream consume the same truth model

### Priority 2 — Unified control layer
- move button actions into a common action adapter
- standardize action result handling
- reduce shell-wrapper inconsistencies

### Priority 3 — Registry/manifest refactor
- define components centrally
- derive dashboards from a shared runtime registry

### Priority 4 — Replay tooling
- continue collecting replay-grade logs
- compare threshold sets against stored history
- avoid tuning by anecdote

---

## Current Known Problems (as of 2026-03-24)

- dashboard/runtime semantics still partially drift around daemon vs job vs recent activity
- some controls remain thin wrappers over scripts rather than standardized component actions
- operator and stream have improved but are not yet fully unified under a single registry
- V2 replay sample is still small; tuning confidence is limited
- output-plane components should be prevented from obscuring core data/trading health

---

## Recommended Next Build Step

Implement a single runtime/component registry and refactor both dashboards to consume it.

This is the structural step most likely to reduce confusion, improve operability, and make the stack reliable enough to control confidently from the dashboard while using a local-first assistant workflow.
