# Center Panel Spec

## Purpose
Define the center panel as the true heart of the stream dashboard.

The center should not remain just a chart container. It should become the main **mission display** of the system: the place where viewers understand what LokiAI is focused on, what matters right now, and what state the machine is in.

This spec defines:
- what the center panel represents
- how chart + mission + trade context should work together
- what it should show when no trade is active
- what it should show when a paper trade is active
- how it should feel on stream

## Core Principle
The center panel is not just visualization. It is the **current mission state** of the machine.

It should answer:
- what is being watched
- what is being traded or considered
- why it matters
- what state the machine is in right now

## Emotional Role
This is the most important panel on the stream.
It should create:
- attention
- tension
- clarity
- a feeling that the machine is actively doing something

Without becoming:
- noisy
- fake-hype
- cluttered
- overexplained

---

# 1. What the center panel should be

## Final identity
The center panel should become a **Tactical Mission Display**.

That means it should combine:
- a real chart
- a current focus asset
- machine state / watch state
- trade context when available
- a small amount of strategic meaning

## It should not become
- a raw trade log
- a static chart with no narrative
- a cluttered collection of overlays

---

# 2. Base center structure

## Layer A — Hero chart
Always present.
This remains the visual anchor.

### Initial implementation
- real BTC-USD 5m chart

### Future flexibility
- selected focus asset
- active paper trade asset
- scanner lead asset
- fallback to BTC-USD when no better focus exists

## Layer B — Mission state overlay
Short text/status that explains what the machine is currently doing.

Examples:
- `WATCH MODE`
- `SCANNER LEAD`
- `PAPER POSITION ACTIVE`
- `NO POSITION • MONITORING`
- `QUALITY GATE ACTIVE`

## Layer C — Focus context
A compact block showing:
- current focus pair
- timeframe
- why it is on screen
- optional last price / live delta

## Layer D — Trade context (when relevant)
When paper trade is active, show a small structured trade summary.

---

# 3. Center panel states

## State 1 — No active trade
### Goal
Still feel alive and intentional.

### Show
- chart
- current focus pair
- mission state like `WATCH MODE`
- reason for focus such as:
  - scanner leader
  - persistence leader
  - live mover watch
  - market anchor

### Tone
- calm
- observant
- disciplined

### Example meaning
"The machine is watching, filtering, and waiting."

---

## State 2 — Scanner focus, no trade yet
### Goal
Show that something is under active consideration.

### Show
- chart of focus asset (if supported later)
- `SCANNER LEAD` or `HIGH PRIORITY WATCH`
- short reason:
  - momentum + persistence
  - live confirmation building
  - Coinbase-actionable watch

### Tone
- active
- focused
- still restrained

### Example meaning
"This is the thing the machine currently cares about most."

---

## State 3 — Active paper trade
### Goal
This is where the stream becomes significantly more compelling.

### Show
- chart
- `PAPER POSITION ACTIVE`
- pair
- entry price
- current price
- unrealized PnL
- time in trade
- maybe thesis / setup tag

### Optional later
- stop / trim zone markers
- time-since-entry indicator
- trade status tag like `RUNNING`, `AT RISK`, `TRAIL ACTIVE`

### Tone
- confident
- precise
- not emotional

### Example meaning
"The machine is currently engaged in a paper position and tracking it live."

---

## State 4 — Post-trade review / cooldown (later)
### Goal
Allow the center to remain meaningful just after a trade closes.

### Show
- recently closed pair
- realized PnL
- outcome label
- back to watch state after a brief interval

### Notes
Not required for first implementation.

---

# 4. What should determine the focus asset

## Initial rule
Keep it simple at first.
Use:
- **BTC-USD** as default anchor

## Later priority order
When the system is richer, the center focus can be chosen by:
1. active paper trade asset
2. top scanner priority asset
3. strongest live Coinbase mover of interest
4. fallback BTC-USD anchor

## Important rule
Do not rotate focus too aggressively. Stream viewers need stability.

---

# 5. Mission overlay content

## Purpose
Give the chart narrative meaning without becoming verbose.

## Good examples
- `WATCH MODE`
- `SCANNER LEAD`
- `PAPER POSITION ACTIVE`
- `NO POSITION • QUALITY GATE ACTIVE`
- `MONITORING COINBASE MOMENTUM`

## Bad examples
- hype slogans
- long paragraphs
- fake urgency
- generic motivational copy

## Tone
This should feel like a command HUD, not a narrator.

---

# 6. Trade summary block

## Purpose
When active, trade context should make the center more compelling without consuming the entire panel.

## Recommended fields
- pair
- side (if relevant)
- entry price
- current price
- unrealized PnL
- time in trade
- setup / thesis tag

## Placement
A small overlay block in a corner or lower edge of the center panel.
Not a separate giant card.

## Style
- compact
- tactical
- high-contrast
- easy to read on stream

---

# 7. Visual behavior

## What the center should feel like
- the windshield
- tactical screen
- primary attention target
- mission console

## Refinement directions
- stronger frame treatment
- subtle live HUD markers
- live price marker later
- maybe thin overlay brackets
- maybe pair/focus chip cluster

## Hard rule
Do not clutter the chart with too many overlays.
The chart must remain readable.

---

# 8. Stream value

## Why this matters
Once the center shows mission/trade state, the stream becomes more watchable because viewers can follow:
- what is being watched
- what the machine is waiting for
- whether a paper position is active
- whether the system is in action or observation mode

This adds narrative without requiring hype.

---

# 9. Build order

## Phase 1
- real chart (done / in progress)
- default pair
- mission state label
- focus context block

## Phase 2
- support active paper-trade state in center
- add compact trade summary block

## Phase 3
- support dynamic focus asset selection
- add better tactical overlays

## Phase 4
- add subtle cinematic polish / animated HUD details

---

# 10. Immediate recommendation
Do not redesign the stream layout.
Use the existing center area and evolve it from:
- chart placeholder
into
- tactical mission display

That is the next correct step for the stream.
