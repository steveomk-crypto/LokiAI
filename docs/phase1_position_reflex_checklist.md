# Phase 1 Implementation Checklist: Fast Position Reflex Layer

Date: 2026-03-26
Status: Build checklist / implementation prep
Related spec: `docs/latency_response_spec.md`

## Purpose

Translate Phase 1 of the latency redesign into an implementation-ready checklist.

Phase 1 goal:
- improve post-entry reaction time,
- reduce dead-hold time,
- react faster when continuation fails,
- do this using local cached state only.

This phase is focused on **open positions only**.

---

## Deliverable Summary

Build a lightweight open-position watchdog that:
- reads open positions and websocket ticker cache,
- evaluates whether continuation is actually happening,
- emits/refines fast actions earlier than the normal loop,
- logs why those actions happened.

It should be additive and narrow.
It should not replace the scanner.
It should not rerank the universe.

---

## New Module

## File to add
- `skills/position-manager/position_reflex_runner.py`

### Why separate from existing position manager
Keep the fast reflex layer isolated from the slower, broader lifecycle logic.

Separation benefits:
- lower implementation risk,
- easier rollback,
- easier debugging,
- easier comparison between fast reflex actions and normal PM actions.

---

## Input Files

### Required
- `paper_trades/open_positions_v2.json`
- `cache/coinbase_tickers.json`

### Likely useful
- `paper_trades/paper_trader_v2_state.json`
- `paper_trades/v2_position_snapshots.jsonl`

### Optional for future enrichment
- `paper_trades/paper_trader_v2_decisions.jsonl`
- `cache/market_state.json`

Phase 1 should avoid depending on heavy external data fetches.

---

## Output / Side Effects

### New log file
- `paper_trades/v2_position_reflex_actions.jsonl`

### Possible state updates to open positions
Allow this layer to update fields such as:
- `trade_state`
- `move_character`
- `remaining_size_pct`
- `last_update`
- `highest_pnl_percent`
- `de_risked_fake_pump`
- `reflex_flags` (new field)
- `reflex_last_action` (new field)
- `reflex_last_reason` (new field)

### Allowed actions in Phase 1
- `HOLD`
- `MARK_AT_RISK`
- `DE_RISK`
- `CLOSE`

Implementation may initially stage this as:
- detect + log first,
- then update state,
- then later allow close if desired.

---

## Position Fields Needed

### Must already exist or be reliably derivable
Each open position should have access to:
- `token`
- `product_id`
- `entry_time`
- `entry_price`
- `current_price`
- `highest_pnl_percent`
- `websocket_drift_300s`
- `websocket_freshness_seconds`
- `confidence`
- `scanner_score`
- `trend`
- `trade_state`
- `move_character`

### New fields to add if missing
These should be written at entry time or backfilled when possible:
- `entry_drift_300s`
- `entry_drift_900s`
- `entry_freshness_seconds`
- `entry_scanner_score`
- `entry_extension_state` (future-friendly)
- `entry_archetype` (future-friendly)
- `reflex_flags` (list)
- `reflex_last_action`
- `reflex_last_reason`
- `reflex_last_timestamp`

For Phase 1, if some entry metadata does not yet exist, fall back gracefully to current position metadata.

---

## Core Evaluation Model

The reflex runner should answer:

### “Given how this trade entered, is it continuing fast enough to justify staying alive?”

This must be evaluated using:
- time since entry,
- current PnL,
- current drift,
- current freshness,
- highest PnL achieved,
- whether expansion occurred at all.

---

## First Reflex Rules to Implement

## Rule Group A: Burst-entry continuation failure

### Purpose
Handle trades entered on already-strong short-term drift that fail to continue.

### Candidate heuristics
A trade can be treated as a burst-sensitive setup if any of these are true:
- very high `entry_drift_300s`
- very high current `websocket_drift_300s` near entry
- high confidence continuation entry
- strong scanner momentum plus rapid immediate movement

### Questions to ask
Within a short post-entry window:
- did PnL expand meaningfully?
- did drift hold or collapse?
- did price stall around entry?

### Likely action path
- no expansion -> `MARK_AT_RISK`
- clear continuation failure -> `DE_RISK`
- obvious collapse -> `CLOSE`

---

## Rule Group B: No-expansion after entry

### Purpose
Detect trades that looked actionable but never actually moved after entry.

### Signals
- highest_pnl remains tiny or zero
- current pnl oscillates near or below zero
- drift weakens quickly
- move_character degrades to stalling/fading

### Intended response
Shorten patience for dead continuation trades.

---

## Rule Group C: Immediate drift collapse

### Purpose
If drift flips sharply after entry, treat that as early invalidation instead of waiting full lifecycle timing.

### Signals
- entry drift strong, then quickly becomes flat/negative
- freshness still current, but move is clearly losing impulse

### Intended response
- mark at risk faster
- close faster on strong collapse

---

## Rule Group D: Fake-pump acceleration

### Purpose
Apply fake-pump logic faster in the reflex layer than the regular loop currently does.

### Signals
- strong burst-style entry
- no real follow-through
- immediate giveback / drift collapse
- weak or zero highest_pnl after hot entry

### Intended response
- de-risk early
- close if failure confirms rapidly

---

## Rule Group E: Stale continuation after entry

### Purpose
If the trade thesis depends on freshness and continuation, stale ticker behavior after entry is a warning sign.

### Signals
- freshness degrades quickly
- no new expansion while freshness worsens
- drift weakens during stale period

### Intended response
- mark at risk
- tighten hold tolerance

---

## Action Flow

## Step 1: Load state
- load open positions
- load websocket ticker cache

## Step 2: For each open position
- map token -> `product_id`
- read latest ticker state
- compute refreshed pnl/current drift/freshness
- compute minutes since entry
- compare current state vs entry state / highest pnl

## Step 3: Classify position reflex condition
Possible internal condition labels:
- `healthy_continuation`
- `stalling_after_entry`
- `burst_failed_to_expand`
- `drift_collapsing`
- `freshness_stale_no_followthrough`
- `fake_pump_likely`

## Step 4: Choose action
- `HOLD`
- `MARK_AT_RISK`
- `DE_RISK`
- `CLOSE`

## Step 5: Persist
- append action record to reflex actions log
- update open position state if action changes state
- update timestamps / last reflex reason

---

## Logging Requirements

### New JSONL record format
Each reflex action log row should include:
- `timestamp`
- `token`
- `product_id`
- `action`
- `reason`
- `trade_state_before`
- `trade_state_after`
- `move_character_before`
- `move_character_after`
- `entry_time`
- `time_in_trade_minutes`
- `entry_price`
- `current_price`
- `pnl_percent`
- `highest_pnl_percent`
- `entry_drift_300s`
- `current_drift_300s`
- `entry_freshness_seconds`
- `current_freshness_seconds`
- `confidence`
- `scanner_score`

### Why this matters
Without this logging, the reflex layer becomes another invisible source of behavior drift.

---

## Integration Plan

## Phase 1A — Detection-only mode
First implementation pass may be detection-only:
- evaluate conditions
- write reflex logs
- do not yet close positions automatically

This creates a safe validation phase.

### Benefits
- see how often rules would fire
- compare against human chart review
- avoid accidental overreaction on first build

## Phase 1B — Stateful mode
After detection-only validation:
- allow state changes (`AT_RISK`, `DE_RISKED`)
- allow size reductions where appropriate

## Phase 1C — Close authority
After confidence improves:
- allow the reflex runner to close positions directly under narrow, explicit conditions

---

## Wiring / Orchestration Options

### Option 1: Add new autonomous task
Add a new task to `autonomous_market_loop.py`:
- `position_reflex`

This keeps it first-class and orchestrated.

### Option 2: Separate daemon/process
Run a standalone lightweight loop for reflex monitoring.

### Recommendation
For implementation simplicity and observability, start with:
### `position_reflex` as a new explicit autonomous task

Later, if needed, it can be split into its own process.

---

## Cadence Recommendation

### Main design target
Run faster than the main market cycle, but only on local state.

### Suggested future cadence
- every 3–5 seconds

This should be tested only after the module exists and logging works.

---

## Safety Constraints

### Must avoid
- full scanner reruns
- external API fanout at reflex cadence
- hidden position closes without logging
- overriding scanner/trader responsibilities

### Must preserve
- clear module boundaries
- reproducible logs
- interpretable state transitions

---

## Minimal MVP Definition

The Phase 1 MVP is complete when:

1. `position_reflex_runner.py` exists
2. it loads open positions and ticker cache
3. it computes continuation-failure conditions
4. it writes `v2_position_reflex_actions.jsonl`
5. it can at least mark positions `AT_RISK` or equivalent
6. behavior is observable and explainable from logs

The MVP does **not** require fully automated closes yet.

---

## Validation Questions

Before allowing direct close authority, validate:
- How often would reflex fire?
- How often would it have improved outcomes on recent bad entries?
- Would it have prematurely attacked good trades?
- Are the late-burst trades actually separable from healthy continuation trades using current local data?

---

## Recommended Immediate Build Sequence

### Build Step 1
Create `skills/position-manager/position_reflex_runner.py`

### Build Step 2
Add loader helpers for:
- open positions
- ticker cache
- safe write helpers for reflex log

### Build Step 3
Implement detection-only evaluation rules:
- no expansion
- drift collapse
- freshness deterioration
- fake-pump acceleration

### Build Step 4
Write reflex log rows without state mutation

### Build Step 5
Review behavior against live/recent examples

### Build Step 6
Enable state mutation for narrow cases

### Build Step 7
Later consider direct close authority

---

## Summary

Phase 1 should be built as a narrow, local, high-speed watchdog for open positions.

It should answer one question better and faster than the current loop:

### “Is this trade actually continuing, or are we just wasting time because we entered late?”

That is the correct first latency improvement target.
