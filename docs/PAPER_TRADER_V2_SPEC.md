# Paper Trader V2 Spec

## Purpose
Define a new paper trader aligned with the current machine instead of the old scanner/trader assumptions.

Paper Trader V2 is not just a paper execution bot. It is a **selective, tiered, guarded, monitored paper trading system** designed to:
- consume the current scanner output carefully
- use Coinbase/live-state confirmation instead of trusting raw scanner output blindly
- manage up to 3 active paper slots
- preserve positive expectancy through aggressive guardrails
- expose clean state for the operator dashboard and stream center
- create a strong foundation for future live readiness without risking capital now

## Core Philosophy
Paper Trader V2 should be:
- selective
- quality-first
- impatient with weak trades
- disciplined about protecting PnL
- aware of move character
- continuously monitored
- easy to inspect from dashboards/stream

It should not be:
- hyperactive
- eager to force trades
- dependent on one crude signal threshold
- blind once a position is opened
- passive about profit protection

---

# 1. System role

## Where it sits in the machine
Paper Trader V2 is downstream of:
- scanner output
- Coinbase websocket/live-state context

And upstream of:
- operator dashboard
- stream center tactical watch
- future reporting/auditing systems

## What it does
- accepts or rejects candidates
- opens paper positions
- manages active slots
- trims / trails / stops / times out positions
- emits structured position state
- allows monitoring and learning layers to evaluate behavior

---

# 2. High-level architecture

Paper Trader V2 should be treated as a layered system, not a monolithic script.

## Layer A — Candidate intake
Consumes scanner output and creates a shortlist.

## Layer B — Entry gate
Applies stricter rules and determines whether a candidate is:
- Tier A
- Tier B
- reject

## Layer C — Position manager
Handles live paper positions using:
- stop losses
- graded profit-taking
- trailing logic
- timeouts
- invalidation exits

## Layer D — Trade state classifier
Continuously classifies active trades by move character:
- steady
- accelerating
- spike
- fake pump
- stalling
- fading

This layer informs position management.

## Layer E — Trade auditor / review layer
Evaluates the trader itself:
- what entries worked
- what entries failed
- whether trims were too aggressive
- whether stops/timeouts were too loose or too tight
- whether fake pumps slipped through
- whether expectancy is degrading or improving

Important: this layer **observes and recommends**. It should not silently rewrite rules.

---

# 3. Slot model

## Max active slots
- **3 active paper positions max**

## Why 3
- aligns with stream center tactical watch design
- keeps the system selective
- avoids overtrading
- makes monitoring cleaner

## Slot behavior
The trader should not force-fill all 3 slots.

Valid states:
- 0 active slots
- 1 active slot
- 2 active slots
- 3 active slots

Holding 0 active slots is acceptable and often desirable if no quality setup exists.

## Slot identity
Each slot should have:
- slot id
- token/pair
- tier
- entry timestamp
- entry price
- current price
- position size
- unrealized PnL
- state label
- reason for entry
- guardrail state

---

# 4. Allowed universe

## Initial V1 universe
Paper Trader V2 should strongly prefer a **Coinbase-actionable universe**.

Why:
- aligns with actual execution constraints
- aligns with current websocket/live-state infrastructure
- aligns with small-account realism
- reduces random scanner junk intake

## Practical rule
V2 should primarily consider names that:
- exist in tracked Coinbase websocket universe
- have fresh websocket state
- are realistically monitorable by the current machine

## DEX names
DEX names can still matter for:
- context
- scanner narrative
- future product intelligence

But V2 should be cautious about taking them directly unless explicitly supported later.

---

# 5. Candidate intake model

## Scanner is discovery, not truth
Current scanner output is broad and noisy. Therefore:
- scanner output should generate candidates
- trader should not trust it directly

## Intake stages
### Stage 1 — Scanner shortlist
Take only a limited top slice of scanner outputs.

Possible selection rules:
- top N by score
- only signals above minimum score threshold
- only high-quality signals

### Stage 2 — Coinbase/live-state cross-check
Candidate must be confirmed by live state where possible.

### Stage 3 — Entry gate
Candidate must pass tier logic before a slot is opened.

---

# 6. Tier model

Paper Trader V2 should classify accepted candidates into:
- **Tier A**
- **Tier B**
- reject

## Tier A
Highest-confidence setups.

### Characteristics
- stronger scanner quality
- better liquidity/volume quality
- stronger or cleaner live confirmation
- cleaner move structure
- less obviously extended
- better fit for the machine's current doctrine

### Practical meaning
Tier A deserves:
- priority in slot allocation
- slightly more room if structure is clean
- more confidence in allowing a runner to continue

## Tier B
Still valid, but less elite.

### Characteristics
- acceptable scanner quality
- acceptable live confirmation
- tradable, but less clean or less ideal than Tier A

### Practical meaning
Tier B should be handled more strictly:
- less tolerance for weak follow-through
- quicker timeout/invalidation
- possibly more conservative sizing/management if sizing is modeled later

## Reject
Anything below Tier B should not be traded.

---

# 7. Entry gate rules

A candidate should pass multiple gates before entry.

## Suggested gate categories
### A. Scanner quality gate
- score above threshold
- candidate not obviously low-quality junk
- scanner reasoning/history not contradictory

### B. Venue/actionability gate
- Coinbase-actionable preference
- symbol present in tracked live universe
- realistic for current system and future small-account discipline

### C. Live confirmation gate
- websocket freshness acceptable
- recent movement confirms asset is alive
- avoid stale symbols

### D. Structure gate
- not pure fake vertical pump
- not obviously exhausted
- move character not already collapsing

### E. Capacity gate
- slot available
- or no valid displacement logic yet in V1

## Important rule
If the gate is not clearly passed, do not open the slot.

---

# 8. Position sizing model

## V1 recommendation
Use fixed paper sizing initially for simplicity and comparability.

Sizing can be standardized per slot, as in earlier system versions, until strategy quality is proven.

## Why fixed size first
- easier attribution
- easier auditing
- easier stream/dashboard interpretation
- removes one extra degree of noise during rebuild

---

# 9. Position management model

Paper Trader V2 should manage open positions actively, not passively.

## Three management families
### A. Loss control
- stop loss
- invalidation exit
- weak-follow-through exit

### B. Profit protection
- staged / graded profit-taking
- runner preservation
- trailing logic
- tightening protection as move matures

### C. Time control
- timeout if trade does not move properly
- timeout if trade stagnates
- timeout if opportunity cost becomes too high

---

# 10. Graded profit-taking

## Principle
Do not dump half the position at the first tiny move.
That cuts winners too early.

## Goal
Use staged profit-taking that:
- locks gains gradually
- preserves upside
- reduces exposure as risk changes
- keeps a runner alive when the move deserves it

## Design intent
A good trade should not be smothered too early.
At the same time, the system should not allow unrealized gains to round-trip back into damage.

## Practical recommendation
Use a **profit ladder** rather than one blunt trim.

### Example philosophy (not fixed numbers yet)
- small first de-risk step after meaningful confirmation
- further trims only as the move proves itself
- leave a runner for continuation
- trail more aggressively as realized gains accumulate

## Tier interaction
### Tier A
- can justify keeping more runner exposure if the move stays clean
- more patience if the move remains steady/healthy

### Tier B
- should lock profits earlier and more aggressively
- less tolerance for giving back strength

---

# 11. Stop loss model

## Principle
A losing or invalidated trade should not be allowed to damage expectancy more than necessary.

## Stop logic should include
### Hard stop
Maximum tolerated adverse move.

### Invalidation stop
Exit when trade thesis clearly breaks, even before a full hard stop.

### Weak-follow-through stop
If the trade never behaves like a valid setup, cut it.

## Tier interaction
### Tier A
May justify a little more structural room if the setup is genuinely stronger.

### Tier B
Should be cut faster if it does not prove itself.

---

# 12. Timeout model

## Principle
Dead trades are dangerous even if they are not deeply red.

They:
- trap slot capacity
- reduce system responsiveness
- slowly erode quality

## Timeout cases
### No movement timeout
Trade fails to move enough after entry.

### Chop timeout
Trade stalls / goes nowhere with no clean development.

### Opportunity cost timeout
Better opportunities exist and the current position is weak/dead.

## Practical rule
A trade should not keep a slot just because it is not yet stopped.

---

# 13. Move-character classifier

This is a critical layer.

## Purpose
The trader should know the character of the move it is in.

Not every green trade is the same.

## Required classifications
- **steady**
- **accelerating**
- **spike**
- **fake pump**
- **stalling**
- **fading**

## Why this matters
Management should differ by move character.

### Examples
#### Steady
- can justify patience
- can justify runner preservation

#### Accelerating
- can justify tightened trailing after confirmation
- strong but must avoid round-trip damage

#### Spike
- may require fast de-risking
- vertical moves are fragile

#### Fake pump
- dangerous
- fast exit candidate
- easy place to lose PnL if trader is naive

#### Stalling
- timeout risk
- weak opportunity cost profile

#### Fading
- trim/exit risk increases
- protection should tighten

## Inputs for move character
Could include:
- short-horizon drift behavior
- persistence behavior
- candle structure
- retracement behavior
- websocket freshness/activity
- scanner trend labels

---

# 14. Duplicate / overlap prevention

## Rule
Trader should avoid redundant or overly correlated entries where possible.

## Examples
- do not repeatedly enter the same token too aggressively after just exiting unless rules explicitly allow it
- avoid wasting multiple slots on essentially the same trade idea unless justified later

This can be simple in V1.

---

# 15. Trader outputs for dashboard/stream

Each active slot should expose enough structured state for:
- operator dashboard
- stream center tactical watch
- later reporting and auditing

## Required slot fields
- slot id
- pair/token
- tier
- entry time
- entry price
- current price
- unrealized pnl percent
- unrealized pnl usd (if useful)
- time in trade
- trade state
- move character
- entry reason
- scanner score at entry
- websocket confirmation snapshot (optional v1)

## Global trader state should expose
- active slot count
- total open exposure (paper)
- aggregate unrealized pnl
- whether trader is in watch mode or engaged

---

# 16. Stream center integration

Paper Trader V2 is directly tied to the stream center evolution.

## Required behavior
### 0 active slots
- center falls back to watch mode
- default chart remains visible
- all 3 slots shown as standby in tactical context

### 1–3 active slots
- center can show primary + secondary slot state
- slot metadata becomes meaningful content
- active count drives mission state

This is why clean trader outputs matter.

---

# 17. Operator dashboard integration

Operator dashboard should eventually show:
- active slots
- slot tiers
- current move character
- trim/stop/timeout state
- trader mode
- slot health

This makes the trader inspectable, not mysterious.

---

# 18. Monitoring layer

## Active trade watcher
This layer should continuously inspect active slots and update:
- current price
- move character
- time in trade
- whether trims/stops/timeouts are being approached

## Why separate it conceptually
Entry and management should not be one blind one-shot action.
A position must remain observed.

---

# 19. Trade auditor / learning layer

## Purpose
Watch the trader itself.

It should evaluate:
- which entries worked
- which failed
- whether Tier A/B definitions are useful
- whether trims were too early
- whether fake pumps slipped through
- whether timeout logic is helping or hurting
- whether expectancy is improving

## Important rule
This layer should:
- observe
- summarize
- recommend

It should **not** silently self-modify the strategy in production.

---

# 20. V1 build recommendation

Paper Trader V2 v1 should focus on:
- 3-slot model
- Tier A / Tier B / reject
- scanner-qualified + websocket-confirmed intake
- stop loss + timeout + graded profit logic framework
- move-character classification stub/basic implementation
- clean state outputs for dashboard/stream

## It should not try to be too smart yet
V1 should be disciplined and inspectable before it becomes clever.

---

# 21. Immediate implementation order

## Phase 1
- define output file/state format
- define slot model
- define A/B tier intake gate
- define basic watch/engaged state

## Phase 2
- implement conservative entry logic
- implement 3-slot management
- implement basic stop/timeout rules

## Phase 3
- implement graded profit-taking model
- implement move-character classification
- improve dashboard/stream output fields

## Phase 4
- add auditor/review layer summaries
- refine thresholds from observed behavior

---

# 22. Final identity

Paper Trader V2 should behave like:
- a selective tactical paper execution system
- guarded by strong risk controls
- aware of move quality
- designed to protect expectancy
- easy to monitor from both the operator dashboard and stream center

That is the target.
