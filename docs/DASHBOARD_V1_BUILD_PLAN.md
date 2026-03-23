# Dashboard V1 Build Plan

## Purpose
Turn the dashboard specs into an implementation sequence that is disciplined, useful, and realistic.

This build plan exists to prevent freestyle UI thrash. The goal is to get a stable, truthful V1 dashboard online first, then expand from there.

## Core Rule
Build the dashboard in the correct order:
1. truth source wiring
2. operator usefulness
3. stream presentation
4. visual polish
5. later controls/performance expansion

Do not start with animation polish before the data layer is trustworthy.

---

# 1. V1 Scope

## V1 includes
### Shared backend reading layer
- file readers/parsers for scanner state
- file readers/parsers for scanner logs
- file readers/parsers for Coinbase websocket state
- file readers/parsers for Coinbase websocket tickers/snapshots
- stale/missing data handling

### Operator dashboard
- health/status top bar
- system health panel
- market state summary panel
- alerts/warnings panel
- top scanner opportunities panel
- scanner persistence/repeat names panel
- scanner run history panel
- Coinbase live movers panel
- Coinbase universe health panel
- websocket activity history panel
- command/controls bay placeholder panel

### Stream dashboard
- branded status banner
- live Coinbase pulse panel
- scanner highlights panel
- system progress panel
- operating-status transparency panel
- latest intelligence/content panel (placeholder/manual text if needed)
- CTA/links panel
- bottom ticker/status strip

## V1 excludes
- real functional control buttons
- trader action controls
- real-money anything
- advanced performance panel unless data is trustworthy
- content publishing controls
- overbuilt animation system
- heavy custom 3D effects

---

# 2. Route / Page Plan

## Page 1: Operator Dashboard
Suggested route:
- `/operator`

Purpose:
Private monitoring and diagnostics.

## Page 2: Stream Dashboard
Suggested route:
- `/stream`

Purpose:
Public-facing 24/7 stream surface.

## Shared structure
Both routes should consume the same backend state loaders and theme system.

---

# 3. Implementation Phases

## Phase 1 — Data layer
### Goal
Make sure the dashboard can read reality before it tries to look cool.

### Tasks
- create shared data loader module(s)
- parse `cache/market_state.json`
- parse `market_logs/YYYY-MM-DD.jsonl`
- parse `cache/coinbase_ws_state.json`
- parse `cache/coinbase_products.json`
- parse `cache/coinbase_tickers.json`
- parse `market_logs/coinbase_ws/YYYY-MM-DD.jsonl`
- create helper functions for stale/missing state
- create derived summaries for persistence, live movers, run history

### Acceptance criteria
- all required files can be read safely
- missing files do not crash the app
- stale conditions are detectable
- derived summaries are coherent

## Phase 2 — Operator dashboard shell
### Goal
Build the useful private view first.

### Tasks
- create operator page layout
- add top status bar
- add system health panel
- add market state summary panel
- add alerts/warnings panel
- add top scanner opportunities panel
- add persistence/repeat panel
- add scanner run history panel
- add Coinbase live movers panel
- add Coinbase universe health panel
- add websocket activity history panel
- add command/controls bay placeholder

### Acceptance criteria
- operator page renders fully from current truth sources
- stale/missing states display clearly
- no panel depends on trader data yet
- page is actually useful for live monitoring

## Phase 3 — Stream dashboard shell
### Goal
Build a clean public-facing view using the same backend truth.

### Tasks
- create stream page layout
- add branded top banner
- add live Coinbase pulse panel
- add scanner highlights panel
- add system progress panel
- add operating-status transparency panel
- add latest intelligence/content placeholder panel
- add CTA/links panel
- add bottom ticker/status strip

### Acceptance criteria
- stream page is readable and coherent
- public-safe data only
- no private controls exposed
- page feels alive even before heavy visual polish

## Phase 4 — Shared theme + sci-fi shell
### Goal
Apply the LokiAI cockpit design language without breaking readability.

### Tasks
- implement dark space/cockpit base theme
- add glass panel styling
- add neon accent system
- add typography system
- add panel border/status glow styles
- add restrained ambient motion
- add stream-specific visual atmosphere

### Acceptance criteria
- pages still read cleanly
- stream view feels cinematic but not cluttered
- operator view stays practical
- performance remains acceptable

## Phase 5 — Refinement
### Goal
Improve quality without changing scope.

### Tasks
- tighten spacing and panel hierarchy
- improve stale-state presentation
- improve live mover sorting/display
- tune CTA placement
- refine command bay placeholder look
- polish stream readability under likely YouTube compression conditions

### Acceptance criteria
- V1 is stable
- V1 is readable
- V1 is presentable on stream
- V1 is useful for operator monitoring

---

# 4. Build Order Inside The Code

## First files / modules to create or refactor
1. shared dashboard data loader/util module
2. operator dashboard page
3. stream dashboard page
4. shared theme/style helpers
5. command bay placeholder component

## Recommended component order
### Operator components first
1. top status bar
2. system health
3. market state summary
4. alerts/warnings
5. top opportunities
6. Coinbase live movers
7. persistence panel
8. run history
9. websocket history
10. command bay placeholder

### Stream components second
1. top banner
2. live pulse
3. scanner highlights
4. system progress
5. operating status
6. latest intelligence
7. CTA panel
8. bottom ticker

---

# 5. Placeholder Strategy

## Command / Controls Bay
V1 behavior:
- render as disabled/locked controls
- operator-only
- visually integrated into cockpit
- no active wiring yet

## Latest Intelligence / Content panel
If no automated feed exists yet:
- use manually populated placeholder text
- or latest known Substack/Gumroad references

## Performance panel
If paper-trading data is not ready/trustworthy:
- show `paper mode / performance panel coming online`
- do not fake precision

---

# 6. Visual Discipline Rules

## Rule 1
No style choice is allowed to reduce readability of core signal panels.

## Rule 2
Operator dashboard gets truth first, aesthetics second.

## Rule 3
Stream dashboard gets cinematic polish, but still must communicate real information fast.

## Rule 4
Stale or missing data should display as a known operational condition, not a broken app.

## Rule 5
Do not block the build waiting for trader reintegration.

---

# 7. Definition of Done for V1
V1 is complete when:
- operator dashboard is live and useful
- stream dashboard is live and presentable
- both read from current scanner/websocket truth sources
- both handle stale/missing data gracefully
- command bay placeholder is present in operator view
- public view exposes no unsafe/private controls
- sci-fi cockpit styling is established without sacrificing clarity

---

# 8. Immediate Next Step
Start implementation with:
- shared data loaders
- operator dashboard first

That is the correct first coding move.
