# Paper Trader Center Spec

## Purpose
Define how the stream center should evolve into a **Paper Trader Tactical Watch** built around the paper trader's active slots.

This spec turns the center from a generic chart/missions panel into a live view of what the machine is actually engaged with.

## Core Principle
The center should reflect the **actual tactical state of the paper trader**.

It should answer:
- are there active paper positions?
- which positions are active?
- which one matters most right now?
- what is the machine currently watching or managing?

This is more compelling than generic charts because it is tied directly to the live state of the system.

---

# 1. Target structure

## Final concept
**Paper Trader Tactical Watch**

The center should support up to **3 paper-trader slots**.

### Design goal
- 1 primary slot
- up to 2 secondary slots
- fallback watch mode when no slots are active

This preserves hierarchy and keeps the center readable on stream.

## Why not 3 equal tiles?
Three equal charts are possible, but weaker.
A hierarchical layout is better because:
- it gives the eye a focal point
- feels more like a command center
- preserves stream clarity
- avoids tiled surveillance-wall clutter

---

# 2. Center states

## State A — No active slots
### Meaning
The paper trader is not currently in any active position.

### Center behavior
- show fallback hero chart (default BTC-USD or chosen anchor)
- show mission state: `WATCH MODE`
- show status: `NO ACTIVE PAPER POSITIONS`
- optionally show current scanner lead or next candidate
- 3 slot positions appear as standby or minimally implied state

### Tone
Calm, disciplined, waiting for quality.

### Example message
- `WATCH MODE`
- `NO ACTIVE PAPER POSITIONS`
- `QUALITY GATE ACTIVE`

---

## State B — 1 active slot
### Meaning
There is one live paper position.

### Center behavior
- one large primary chart for the active slot
- two standby slot states
- primary slot metadata visible

### Why this works
The stream has clear focus without feeling empty.

---

## State C — 2 active slots
### Meaning
Two paper slots are currently in play.

### Center behavior
- one primary slot chart
- one secondary slot chart
- one standby slot

### Notes
The primary slot should be visually dominant.
The secondary slot should be visible but smaller.

---

## State D — 3 active slots
### Meaning
All configured paper slots are active.

### Center behavior
- one primary slot chart
- two secondary slot charts
- all three slots visible simultaneously

### Notes
This is the fully engaged tactical state.

---

# 3. Slot priority logic

## Goal
Decide which active slot becomes the **primary** center focus.

## Recommended v1 rule
Use:
- **most recently opened active slot = primary**

### Why
- simple
- deterministic
- feels live/current
- easy to explain

## Possible future rules
- highest unrealized risk/opportunity
- biggest unrealized move
- highest-conviction setup
- manually pinned focus

But v1 should stay simple.

---

# 4. Slot states

## Active slot
### Show
- pair
- chart
- entry price
- current price
- unrealized PnL
- time in trade
- trade state label

### Trade state label ideas
- `ACTIVE`
- `TRAILING`
- `AT RISK`
- `RUNNING`

V1 can start with just `ACTIVE`.

## Standby slot
### Show
- slot number or placeholder card
- label: `STANDBY`
- sublabel: `WAITING FOR SETUP`

### Purpose
Keep the tactical layout stable even when not all slots are filled.

---

# 5. Metadata per active slot

## Required v1 fields
- `pair`
- `entry_price`
- `current_price`
- `unrealized_pnl`
- `time_in_trade`
- `slot_state`

## Nice-to-have later
- stop level
- trim/trail state
- trade thesis/setup tag
- scanner score at entry
- persistence at entry

---

# 6. Chart behavior per slot

## V1 recommendation
Use available chart data for the active slot where possible.

### If slot pair is chartable
- render a real chart for that slot

### If slot pair is not yet supported
- show placeholder chart shell + metadata block
- do not break the layout

## Fallback rule
No active slots → fallback to default anchor chart (BTC-USD)

---

# 7. Mission-state overlay

## Purpose
The center should still retain a tactical identity, not become just charts and numbers.

## Suggested top-level center states
- `WATCH MODE`
- `PAPER POSITION ACTIVE`
- `MULTI-SLOT MONITORING`
- `QUALITY GATE ACTIVE`

## Rule
Short, command-like, readable, not verbose.

---

# 8. Public stream value

## Why this is stronger
This center concept makes the stream more watchable because viewers can follow:
- whether the machine is engaged
- what it is engaged in
- which position matters most
- whether slots are filling or empty

This creates natural narrative tension without fake hype.

---

# 9. Visual structure recommendation

## Recommended center layout
### With active slots
- one large primary display
- two smaller secondary/standby displays
- tactical metadata overlays

## With no active slots
- one hero fallback chart
- mission-state overlay
- subtle standby indication for empty slots

## Rule
The center must keep a clear focal point even when multiple slots are visible.

---

# 10. Build order

## Phase 1
- detect active paper slots
- define primary slot by simple rule
- show watch mode when empty

## Phase 2
- render primary active slot in center
- render secondary/standby slot cards
- show metadata for active slot(s)

## Phase 3
- support real charts per slot where possible
- improve tactical overlays

## Phase 4
- add richer slot state labels / trade-state logic

---

# 11. Immediate recommendation
Do not implement blindly from the current center.
Use this spec to evolve the center into:
- a tactical slot watch
- with fallback watch mode
- with one clear primary focus

That is the correct next evolution of the stream hero.
