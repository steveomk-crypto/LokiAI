# Profit Ladder Spec

## Purpose
Define how Paper Trader V2 should take profits without cutting winners too early or allowing good trades to round-trip into damage.

This spec exists because fixed percentages alone are not enough. Profit-taking should be structured, but it also needs to respond to the character of the move and the broader market context.

## Core Principle
The system should:
- protect PnL progressively
- preserve a runner when the move deserves it
- de-risk quickly when the move is weak, spiky, or fake
- avoid dumping too much size too early on strong trades

This is not about taking profits at random percentages.
It is about using a **base ladder + market-sensitive adjustment**.

---

# 1. Base structure

## Use a 3-step profit ladder
This is the default structure for V2.

### Why 3 steps
- 2 steps is too blunt
- 4+ steps adds complexity too early
- 3 steps gives enough room for:
  - early de-risk
  - mid-trade protection
  - runner preservation

## Base logic
The trader should think in terms of:
- Trim 1
- Trim 2
- Trim 3
- then runner/trailing management

---

# 2. Explicit trim amounts

The ladder should not just track that a trim level was reached. It should define what is actually reduced.

## Recommended default sizing behavior
### Initial position
- 100%

### After Trim 1
- reduce to **75% remaining**
- purpose: first de-risk, but keep most of the position alive

### After Trim 2
- reduce to **50% remaining**
- purpose: lock meaningful gains and reduce emotional/structural risk

### After Trim 3
- reduce to **35% remaining**
- purpose: keep a medium runner, not a token dust runner

## Why these numbers
They match the desired philosophy:
- protect some PnL
- do not overcut early
- keep enough runner for a real move to matter

---

# 3. Tier-aware base ladder

## Tier A
Tier A trades deserve more patience if the structure remains healthy.

### Suggested base thresholds
- Trim 1 at **+1.5%**
- Trim 2 at **+3.0%**
- Trim 3 at **+5.0%**

### Interpretation
Tier A should not be trimmed too aggressively too early if the move remains steady/clean.

## Tier B
Tier B trades should prove themselves faster and give the system less reason to be patient.

### Suggested base thresholds
- Trim 1 at **+1.0%**
- Trim 2 at **+2.0%**
- Trim 3 at **+3.5%**

### Interpretation
Tier B should be de-risked faster and trailed more tightly.

## Important note
These base thresholds are not final truth. They are the starting ladder. Real behavior should be adjusted by trade/market context.

---

# 4. Market-sensitive adjustment layer

This is the most important part.

## Base ladder is not enough
The same percentage move does not mean the same thing in every market.

Examples:
- for one asset, +2% may be meaningful follow-through
- for another, +2% is noise inside a broader impulse
- for a fake pump, +2% can vanish instantly

So the trader must adjust trim aggressiveness based on current conditions.

---

# 5. Move-character categories

The profit ladder should respond to move character.

## Required move-character categories
- **steady**
- **accelerating**
- **spike**
- **fake pump**
- **stalling**
- **fading**

## Why this matters
A steady climb should not be treated like a vertical social-media pump.

---

# 6. Profit ladder behavior by move character

## Steady
### Meaning
The trade is climbing in a controlled, healthy way.

### Suggested profit behavior
- allow the base ladder to operate normally
- keep runner room
- avoid overreacting

### Trail behavior
- activate after Trim 1
- tighten after Trim 2 as normal
- do not panic-trail too aggressively if the move remains clean

---

## Accelerating
### Meaning
The trade is working strongly and gaining momentum.

### Suggested profit behavior
- still take Trim 1 when appropriate
- allow more patience after that than a weak move would deserve
- preserve runner exposure if follow-through remains strong

### Trail behavior
- activate after Trim 1
- tighten after Trim 2, but not so tightly that the move is strangled immediately

### Risk
Acceleration can become a spike. Monitoring matters.

---

## Spike
### Meaning
The move is sharp and vertical, but not yet clearly fake.

### Suggested profit behavior
- de-risk faster
- be more willing to lock gains early
- do not assume the move will stay healthy

### Trail behavior
- activate quickly
- tighten faster than with steady moves

### Risk
A spike can become a fake pump very quickly.

---

## Fake pump
### Meaning
The move is behaving in a way that suggests unsustainable pumping / likely reversal risk.

### Suggested profit behavior
- immediate de-risk step
- reduce exposure quickly
- preserve only a controlled runner if any

### Exit behavior
If weakness confirms after the de-risk step:
- full exit

### Rule
Fake pumps are not where the trader should get heroic.

---

## Stalling
### Meaning
The move is not progressing meaningfully.

### Suggested profit behavior
- if in profit, protect it more aggressively
- if barely positive, do not let the trade drift forever
- be willing to timeout or flat-exit weak situations

### Rule
A trade that stops proving itself should lose room quickly.

---

## Fading
### Meaning
The move is weakening after entry or after partial success.

### Suggested profit behavior
- tighten protection
- if already trimmed, protect the runner more aggressively
- if post-spike fade confirms, exit

---

# 7. Trail model

## Activation
Trail should turn on:
- **after Trim 1**

## Tightening
Trail should tighten:
- **after Trim 2**

## Tier-aware trail defaults
### Tier A
- more room
- less eager to suffocate the move

### Tier B
- tighter trail
- less forgiveness

## Conceptual role
The trail is there to stop good unrealized gains from fully leaking away.
It is not there to suffocate every healthy continuation.

---

# 8. Runner philosophy

## Goal
A runner should still matter.

## Bad runner
- too tiny to matter
- emotionally/financially irrelevant
- only there for optics

## Good runner
- meaningful enough to benefit from a strong continuation
- small enough that damage is controlled if the move rolls over

## Recommended v1 runner size
After 3 trims:
- keep roughly **35%** remaining

This is a **medium runner**.

---

# 9. Market regime awareness

The trader should not assume all markets behave the same way.

## Regime categories (conceptual)
- sleepy / low-range
- normal / balanced
- expanding / strong
- unstable / pumpy

## Why it matters
### Sleepy market
- trim earlier
- trail tighter
- do not expect huge extension

### Expanding market
- allow stronger continuation
- preserve runner longer if move remains healthy

### Unstable/pumpy market
- de-risk faster
- do not get greedy

## V1 recommendation
Regime can start as a soft adjustment signal rather than a full complex engine.

---

# 10. Cross-reference logic

This is the key design rule.

The trader should not ask only:
- `is pnl above threshold?`

It should also ask:
- what is the move character?
- what is the market regime?
- is this Tier A or Tier B?
- has the trade already become fragile?
- is this healthy continuation or fake pumping?

## Translation
Profit management should be:
- percentage-aware
- character-aware
- context-aware

---

# 11. Required state fields

To make this inspectable, the trader should expose:
- `highest_pnl_percent`
- `trim_step`
- `trail_active`
- `trail_distance_pct`
- `remaining_size_pct`
- `de_risked_fake_pump`
- `move_character`
- `trade_state`
- discrete trim event logs later

These fields are necessary for both debugging and dashboard/stream use.

---

# 12. Trade-state labels

Suggested trade-state labels should include:
- `ACTIVE`
- `TRIM_1`
- `TRIM_2`
- `TRIM_3`
- `DE_RISKED`
- `TRAILING`
- `CLOSED`

This will make the trader much more intelligible on dashboards and stream overlays.

---

# 13. Logging requirements

Every meaningful profit-management event should eventually be logged explicitly.

## Events to log
- trim 1 reached
- trim 2 reached
- trim 3 reached
- trail activated
- trail tightened
- fake-pump de-risk
- trailing exit
- fade exit

## Why
This is essential for:
- auditing
- improving the system
- explaining behavior later
- building stream/dashboard context

---

# 14. V1 implementation guidance

## Good first implementation
- explicit trim thresholds
- explicit remaining size transitions
- trail after Trim 1
- tighter trail after Trim 2
- fake-pump de-risk path
- stronger Tier B behavior

## What not to overcomplicate immediately
- too many trim tiers
- fully dynamic regime engine
- overly clever adaptive math before the basics are observable

---

# 15. Final identity

The profit ladder should behave like:
- a disciplined gain-protection system
- not a panic seller
- not a lazy bag-holder
- not a rigid percentage toy

It should protect PnL while still letting real winners matter.

That is the target.
