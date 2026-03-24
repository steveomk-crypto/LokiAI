# Dashboard Go-Live Spec

Updated: 2026-03-24

## Purpose

This document defines the final intended UX, visual hierarchy, copy style, status vocabulary, control behavior, and launch-readiness criteria for the operator dashboard and stream dashboard.

This spec is separate from `docs/control-stack-spec.md`.

- `control-stack-spec.md` defines architecture and runtime truth.
- `dashboard-go-live-spec.md` defines how that truth should be presented to humans.

The goal is to make both dashboards:
- trustworthy
- readable fast
- internally consistent
- usable under pressure
- presentation-safe for live/public viewing when appropriate

---

## Dashboard Roles

## 1. Operator Dashboard

### Audience
- primary operator
- system maintainer
- strategy/debugging user

### Purpose
- inspect runtime truth
- control components safely
- identify blockers quickly
- understand what happened recently
- manage the stack without opening multiple terminals/logs unless necessary

### Design priority
1. correctness
2. control clarity
3. dependency visibility
4. actionable status
5. density without chaos

### Tone
- technical
- direct
- compact
- not hype
- not theatrical

The operator dashboard should feel like a control surface, not a marketing page.

---

## 2. Stream Dashboard

### Audience
- passive viewer
- operator in monitoring mode
- possible public/live audience

### Purpose
- show current tactical market picture
- show current system posture
- present confidence and structure without exposing internal mess
- give a readable “what is happening now” surface in under ~3 seconds

### Design priority
1. legibility
2. confidence
3. visual hierarchy
4. public-safe copy
5. presentation stability

### Tone
- polished
- restrained
- “mission control”
- not nerd soup
- not hype-beast nonsense

The stream dashboard should feel deliberate and broadcast-ready.

---

## Shared UX Principles

1. **One truth model**
   - operator and stream must derive status from the same underlying runtime state.

2. **Small status vocabulary**
   - avoid semantic drift and label explosion.

3. **Fast scanability**
   - user should understand overall state quickly.

4. **Visible blockers**
   - blocked or degraded components must stand out.

5. **No fake certainty**
   - when a component is inferred healthy from recent data rather than PID/process state, wording must remain truthful.

6. **No dead decorative copy**
   - repeated disclaimers and placeholder text reduce clarity.

---

## Canonical Status Vocabulary

All UI-facing component state should collapse into a small set.

### Allowed top-level labels
- `RUNNING`
- `ACTIVE`
- `IDLE`
- `BLOCKED`
- `DEGRADED`
- `FAILED`

### Intended meaning

#### RUNNING
- persistent service/process is actively resident and healthy

#### ACTIVE
- component is not necessarily continuously resident, but recently completed useful work or is operationally active

#### IDLE
- component is not currently active and nothing indicates urgent mismatch

#### BLOCKED
- component cannot safely or correctly operate because dependencies are not healthy

#### DEGRADED
- partially working, stale, lagging, or inconsistent with ideal health

#### FAILED
- recent action or recent cycle clearly failed

### Internal status strings
Internal detail strings may still exist, but the dashboard should map them into this smaller vocabulary for primary display.

---

## Operator Dashboard Layout Spec

## Top Strip

Must include:
- global mode
- scanner freshness
- feed/websocket health
- main loop status
- active alerts count
- optionally current time / refresh recency

### Rules
- top strip is for immediate operator orientation only
- no more than 6–8 badges
- badges should represent the system’s major truth, not implementation trivia

---

## Main Sections

Operator layout should be organized in this order:

### 1. Data Plane
Cards:
- Coinbase Feed
- Market Scanner
- Market State Freshness (if separated)

### 2. Trading Plane
Cards:
- Paper Trader V2
- Position Manager
- Open slot summary / trade summary

### 3. Orchestration
Cards:
- Main Loop
- Last cycle summary
- task success/failure summary

### 4. Output Plane
Cards:
- broadcaster
- telegram sender
- x autoposter
- performance analyzer
- sidecars/loggers

### 5. Diagnostics / Alerts
Cards:
- active warnings/errors
- recent action results
- cycle failures
- last error summaries

---

## Operator Card Spec

Every card should include:

1. **Component name**
2. **Component type** (`SERVICE`, `JOB`, or `MODE`)
3. **Observed state**
4. **Desired state**
5. **Mismatch indicator** if desired != observed
6. **Dependency status**
7. **Last success time**
8. **Last error**
9. **Last action result**
10. **Controls**

### Controls by type

#### Service cards
- Start
- Stop
- Restart
- Inspect

#### Job cards
- Run now
- Inspect

#### Mode cards
- Enable / disable / set mode

### Dangerous actions
Dangerous actions (flatten, destructive resets, etc.) must:
- use distinct styling
- be visually isolated from normal run/start controls
- make scope clear (`Flatten V2`, not just `Flatten`)

---

## Operator Copy Rules

### Good copy
- `Blocked by dependencies: market_scanner`
- `Last success: 12:42:11`
- `Loop cycle failed: FileNotFoundError`

### Bad copy
- fluffy explanations
- repeated beta disclaimers in multiple cards
- placeholders that say nothing useful
- overdecorated “mission” language on the operator page

### Tone rule
Operator copy should explain the machine, not narrate drama.

---

## Stream Dashboard Layout Spec

## Overall layout
Three-column broadcast layout is acceptable, with:
- left rail = live market/input context
- center = primary tactical focus
- right rail = system posture / supporting status

### Center priority
The center must answer:
- what is the focus asset/setup now?
- what is the paper trader doing now?
- what is the market doing now?

### Left rail priority
The left rail must answer:
- what names are moving?
- what names are scoring?

### Right rail priority
The right rail must answer:
- is the system healthy?
- is the system live/active/blocked?
- what is the current mode?
- what is the latest supporting context?

---

## Stream Dashboard Content Rules

### Keep
- live movers
- scanner highlights
- main tactical visualization
- concise runtime posture
- minimal supporting intelligence / distribution info

### Reduce / remove
- repeated disclaimers
- internal implementation junk
- multiple panels saying the same thing
- overly long explanatory text
- too many tiny status rows with near-duplicate meaning

### Public-safe rule
A viewer should understand the stream without needing to know:
- internal filenames
- exact daemon structure
- PID/process trivia
- refactor history

---

## Stream Copy Rules

### Desired tone
- calm
- sharp
- restrained
- technical enough to sound credible
- not too internal

### Example good copy
- `Paper-only mode`
- `System posture: ACTIVE`
- `Watching for confirmed continuation`
- `No live slot yet`

### Example bad copy
- repeated mentions of rebuild/beta on multiple cards
- overhyped status phrasing
- internal debugging language like `active recently` on public-facing panels

---

## Visual Hierarchy Rules

## Operator
- use stronger emphasis for blockers, mismatches, and failures
- use lower emphasis for logs/notes/metadata
- card density is okay if scannability remains high

## Stream
- strongest contrast should go to:
  - primary focus / mission state
  - market movement
  - system posture
- supporting text should be clearly secondary
- avoid dense, low-value microtext unless it materially helps decisions

---

## Color / Emphasis Rules

### Green / healthy
Only for genuinely good or desired states.

### Yellow / warning
Use for:
- mismatch
- stale state
- blocked but recoverable
- degraded conditions

### Red / failed
Use for:
- recent errors
- genuine failure states
- disconnected or broken critical dependencies

### Neutral / info
Use for:
- timestamps
- metadata
- passive labels

Avoid status-color inflation where everything is “important.”

---

## Desired-State UX Rules

Desired state must be visible on operator cards.

### Examples
- feed desired = `ON`
- main loop desired = `ON`
- scanner desired = `AUTO`
- paper trader desired = `AUTO`

### Mismatch behavior
If desired state is not satisfied:
- card elevates to warning
- mismatch label is explicit
- control buttons should help resolve, not confuse

Desired state must not feel decorative. It should mean something operational.

---

## Dependency UX Rules

Dependency health should be visible but concise.

### Allowed card phrases
- `deps ok`
- `blocked by: coinbase_feed`
- `blocked by: market_scanner, coinbase_feed`

### Rules
- dependency issues should disable invalid actions where appropriate
- downstream cards should not pretend to be healthy when their blockers are red

---

## Main Loop UX Rules

The main loop has caused repeated confusion and needs special presentation care.

### Operator display should distinguish:
- daemon/process resident
- recent cycle activity
- most recent cycle outcome

### Recommended primary operator display
- `Main Loop • RUNNING`
- `Main Loop • ACTIVE`
- `Main Loop • IDLE`
- `Main Loop • FAILED`

### Additional detail rows
- daemon resident
- last cycle start
- last cycle end
- last completed task
- last error

### Stream display
The stream should show a simplified loop state, not internal daemon semantics.
Preferred:
- `Main loop: ACTIVE`
- `Last cycle: RECENT`

Not:
- low-value daemon/process trivia unless it directly matters to meaning

---

## Live Readiness Checklist

The dashboards are “go-live ready” only if all are true:

### Stability
- no 500 errors
- no stale key crashes
- no obvious race conditions at load
- no broken control buttons

### Truthfulness
- no contradictory major statuses
- no major component shown healthy when upstream is clearly broken
- no public-facing panel exposing misleading internal semantics

### Usability
- operator can manage core services/jobs from dashboard
- blocked actions are visibly blocked
- recent errors are visible
- last actions are visible on relevant cards

### Presentation quality
- no placeholder filler copy left in primary panels
- no repeated disclaimers across multiple panels
- no visual overflow/clipping in intended viewport
- stream can be shown publicly without explanation of internal architecture

---

## Final Polish Priorities

### Priority 1 — Status simplification
Map internal status details to the canonical vocabulary.

### Priority 2 — Copy cleanup
Shorten and unify copy on both dashboards.

### Priority 3 — Card hierarchy polish
Make the most important states visually strongest.

### Priority 4 — Stream public-safe pass
Remove internal/debuggish leftovers.

### Priority 5 — Operator action ergonomics
Ensure every important control is obvious and safe.

---

## Recommended Implementation Order

1. standardize visible status labels
2. clean operator card subtitles/metadata
3. simplify stream right rail copy
4. tighten stream panel hierarchy
5. ensure all controls are wired and labeled cleanly
6. run final live-readiness walkthrough

---

## Definition of Done

The dashboard work is done when:
- operator dashboard is trustworthy and quick to operate
- stream dashboard is polished enough to leave on-screen confidently
- runtime/control semantics are consistent between both views
- no critical component requires terminal access for normal operation
- UI language feels intentional rather than accreted

That is the bar for “ready to go live.”
