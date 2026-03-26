# Latency & Response-Time Improvement Spec

Date: 2026-03-26
Owner: LokiAI / operator
Status: Draft for implementation planning

## Purpose

Improve the market loop's practical response time without turning the entire system into a high-frequency batch loop.

This spec is based on current live behavior and code inspection of:
- `autonomous_market_loop.py`
- `skills/market_scanner/market_scanner.py`
- `skills/paper-trader/paper_trader_v2.py`
- `skills/position-manager/position_manager.py`
- websocket/ticker cache usage

The goal is not merely to reduce the global loop interval. The goal is to reduce **effective decision latency** at the right parts of the stack.

---

## Current Architecture Summary

### Active pipeline today
1. Coinbase websocket feed updates cached ticker state continuously.
2. `market_cycle_daemon.sh` orchestrates periodic tasks.
3. `autonomous_market_loop.py` dispatches tasks such as:
   - `market_scanner`
   - `paper_trader`
   - `position_manager`
4. `market_scanner` builds scanner candidates and writes market state.
5. `paper_trader_v2` uses scanner state + websocket/ticker state to open positions.
6. `position_manager` manages open positions and may trigger a follow-up paper trader run if closures happen.

### Important current reality
The system already has:
- a continuous websocket feed
- separated scanner/trader/position-manager modules
- shared cache/state files

But it still behaves mostly like a **batch loop system using live data**, rather than a truly event-driven system.

---

## Problem Statement

Recent live behavior suggests the system is:
- finding active symbols more reliably than before,
- but still often entering after the main impulse is already visible,
- and then managing those entries too slowly or too patiently after the burst has already spent itself.

This creates a repeated pattern:
1. candidate becomes strong,
2. trader enters on confirmation,
3. post-entry move fails to continue,
4. trade stalls / fades / fake-pumps,
5. slot remains occupied too long relative to the move quality.

The root latency problem is distributed across the pipeline. It is not only the 30-second global loop interval.

---

## Design Principles

### Principle 1: Keep the scanner slower than the action layers
The scanner should remain the slower filtering/selection brain.

### Principle 2: Trader should trigger faster than the scanner
The trader should react quickly once a symbol is already known-good enough to watch.

### Principle 3: Position management should be the fastest layer
Open-position reaction time should be faster than scanner/trader cadence because open risk is more time-sensitive than initial discovery.

### Principle 4: Reduce latency with local cached state first
Prefer websocket/cache-driven fast paths before adding more external API calls or full-universe rescans.

### Principle 5: Different entry archetypes need different post-entry timing rules
Late continuation entries should not be managed the same way as early reclaim entries.

---

## Target Architecture

### Desired sequencing model
- **Scanner** = slower universe builder / ranker
- **Trader** = medium-speed trigger for qualified names
- **Position manager** = fast reflex loop for open positions

Practical interpretation:
- full scanner can remain at current or near-current cadence,
- trader should gain a fast path for already-qualified candidates,
- position manager should gain a fast monitoring path for open positions.

---

## Phase 1: Fast Position Reflex Layer

### Goal
Reduce the time between:
- a late or unstable entry,
- and the system recognizing that the trade has failed to continue.

### Why first
This is the best initial latency improvement because it:
- reduces slot waste,
- reduces dead-hold time,
- improves downside control,
- requires no full-universe rescoring.

### Scope
Applies only to **open positions**.

### Proposed behavior
Create a fast monitor path that runs more often than the main market loop and only reads:
- websocket/ticker cache,
- current open positions,
- position state.

### Fast checks for open positions
For each open position, evaluate:
- drift collapse after entry,
- no-expansion after burst entry,
- freshness degradation,
- immediate move character transition (building -> stalling/fading),
- post-entry gain failure after high-drift entry.

### Intended response logic
Examples of actions this layer may eventually support:
- downgrade position faster,
- reduce size earlier,
- tighten leash on late-burst entries,
- close obviously dead continuation attempts sooner.

### Data sources
Use only local/cache data when possible:
- `cache/coinbase_tickers.json`
- `paper_trades/open_positions_v2.json`
- existing position metadata in V2 state/logs

### Non-goals
- do not re-run full scanner
- do not fetch broad external market data every few seconds
- do not change scanner ranking in this phase

---

## Phase 2: Armed Candidate / Fast Trigger Layer

### Goal
Reduce entry delay between:
- scanner qualification,
- and trader execution.

### Current gap
A symbol may be good enough to act on, but the system still waits for the next batch-style opportunity to open.

### Proposed state machine
Add an intermediate candidate lifecycle:
- `detected`
- `qualified`
- `armed`
- `triggered`
- `invalidated`

### Meaning
- `detected`: scanner sees the symbol
- `qualified`: scanner/ranker believes it is worth trader attention
- `armed`: symbol is eligible for a faster trigger path using websocket state
- `triggered`: trader actually opens
- `invalidated`: symbol loses the setup before trigger

### How it should work
Scanner does not immediately need to open a trade.
Instead it can write a short-lived armed list of symbols with:
- expiry time,
- trigger class,
- required confirmation rules,
- invalidation rules.

Then a faster local trigger runner checks those names using websocket/ticker cache only.
If armed conditions remain valid and trigger conditions are met, entry can happen without waiting for another full scanner cycle.

### Benefits
- faster entries on already-approved candidates,
- lower handoff latency,
- preserves scanner discipline while improving trader speed.

---

## Phase 3: Entry Archetype Tagging

### Goal
Stop managing all trades as if they are the same kind of setup.

### Problem
Recent live behavior suggests many entries are effectively late continuation/burst entries, but they are not being managed with a short enough leash.

### Proposed archetypes
At minimum:

#### 1. Early reclaim / fresh setup
Characteristics:
- fresher structure,
- not already vertical,
- cleaner reset/reclaim behavior,
- more room for follow-through.

Management implication:
- allow more time/space before invalidation.

#### 2. Late continuation / burst setup
Characteristics:
- already-large short-term drift,
- visually obvious impulse underway,
- more likely to fake-pump or stall if late.

Management implication:
- require fast continuation,
- invalidate sooner,
- do not tolerate long dead air after entry.

### Implementation shape
When trader opens a position, record fields such as:
- `entry_archetype`
- `entry_extension_state`
- `entry_trigger_class`

Position manager can then interpret post-entry behavior differently based on archetype.

---

## Phase 4: Scanner Fast-Path Refresh (Optional / Later)

### Goal
Improve responsiveness for relevant symbols without globally increasing scanner cost.

### Approach
Keep the main scanner cycle relatively slow, but add a smaller/faster refresh path for symbols that are already relevant:
- armed symbols
- current leadership/ranked symbols
- open-position symbols

### Constraints
This should use:
- websocket cache,
- existing market_state,
- lightweight local state,

and avoid:
- full broad rescans,
- repeated heavy external API pulls.

### Why later
This is useful, but should only come after:
- fast open-position monitoring,
- armed candidate logic,
- archetype-aware management.

---

## Recommended Rollout Order

### Order of implementation
1. **Fast Position Reflex Layer**
2. **Armed Candidate / Fast Trigger Layer**
3. **Entry Archetype Tagging**
4. **Optional scanner fast-path refresh**

### Why this order
- fastest practical benefit first,
- lowest architectural disruption first,
- lets later entry-speed changes happen with better risk control.

---

## Spec for Fast Position Reflex Layer (Detailed)

### New component
Possible names:
- `position_reflex_runner`
- `fast_position_monitor`
- `position_watchdog_v2`

### Inputs
- `paper_trades/open_positions_v2.json`
- `cache/coinbase_tickers.json`
- optional position metadata from V2 state/logs

### Cadence
Faster than the main loop.
Target idea for later implementation:
- every 3–5 seconds, or event-like polling cadence using local cache

### Allowed actions
- update move character faster
- mark at-risk sooner
- de-risk sooner
- close sooner when post-entry continuation clearly fails

### Required metadata additions (future)
Each open position should ideally carry:
- `entry_archetype`
- `entry_drift_300s`
- `entry_drift_900s`
- `entry_freshness_seconds`
- `entry_trigger_class`
- `first_followthrough_deadline`
- `late_entry_flag`

### Core reflex checks to support
- no meaningful expansion within short post-entry window
- drift collapse after high-drift entry
- move_character degrading quickly after entry
- freshness becoming stale too quickly for continuation thesis
- no new highs / no positive impulse after late continuation entry

---

## Spec for Armed Candidate Layer (Detailed)

### New state file
Possible path:
- `cache/armed_candidates.json`

### Candidate record fields
- `token`
- `product_id`
- `armed_at`
- `expires_at`
- `scanner_score`
- `entry_archetype_candidate`
- `trigger_rules`
- `invalidate_rules`
- `source` (scanner / ranked / bridge)

### Trigger path behavior
A fast runner checks armed candidates against local websocket/ticker state and can:
- trigger open,
- keep armed,
- invalidate and remove.

### Trigger rules examples
These are conceptual, not implementation-approved yet:
- reclaim maintained
- drift stays above required level
- freshness remains current
- no immediate collapse after arm time

### Invalidate rules examples
- drift flips negative too fast
- freshness stale beyond threshold
- price no longer near valid trigger zone
- move already too extended beyond allowed entry state

---

## State Ownership / Module Boundaries

### Scanner owns
- universe selection
- rank and candidate quality
- initial qualification for armed state

### Trader owns
- final entry open action
- classification of entry type
- slot usage / open-position creation

### Position reflex / manager owns
- rapid post-entry monitoring
- continuation validation
- fast invalidation / de-risking
- later lifecycle handling

This boundary keeps the system understandable and reduces cross-module confusion.

---

## Latency Sources Identified in Current System

1. **Scanner detection cadence latency**
2. **Promotion latency from scanner to trader**
3. **Confirmation/persistence latency**
4. **Trader execution waiting on batch timing**
5. **Position-manager reaction latency after entry**
6. **Data-model mismatch between scanner/trader/PM timing assumptions**

This spec addresses those in order of likely practical impact.

---

## Success Criteria

### Operational success
- fewer trades that immediately stall after entry
- faster recognition of failed continuation
- less time spent in dead or fake-pump trades
- better slot turnover under weak follow-through

### Structural success
- scanner remains disciplined without needing global hyper-fast cadence
- trader can act faster on already-qualified names
- open-position reaction is faster than initial discovery

### Observability success
Need future instrumentation for:
- time from scanner qualification to arm
- time from arm to trigger
- time from entry to first expansion / failure
- time from failure signature to PM action

---

## What Not To Do First

### Do not first reduce the entire loop interval globally
Reason:
- this increases churn/cost/noise,
- but does not fix architecture-level handoff latency by itself.

### Do not first make scanner fully event-driven
Reason:
- too much blast radius,
- scanner should remain the slower filtering layer unless proven otherwise.

### Do not first add more confirmation rules
Reason:
- recent problems already suggest too much delay / over-confirmation in some contexts.

---

## Immediate Recommendation

If implementation starts, begin with:

### Phase 1: Fast Position Reflex Layer
because it offers the best mix of:
- lower complexity,
- direct benefit,
- lower risk,
- better control of current late-entry pain.

After that, implement:

### Phase 2: Armed Candidate / Fast Trigger Layer
so the system can reduce entry delay without making the full scanner loop hyperactive.

---

## Final Summary

The best latency improvement is **not** simply shrinking the whole loop interval.

The best architectural improvement is:

### slow scanner, fast trader trigger, fastest position reflex

That preserves selection discipline while improving the parts of the system that actually need to move quickly.
