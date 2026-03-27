# Post-Trade Suppression Fix Plan — 2026-03-27

## Objective
Reduce self-inflicted no-trade windows caused by over-sticky post-trade suppression while preserving the original goal: stop revenge re-entry, same-name churn, and blind leader recycling.

This plan is based on live run evidence from the 2026-03-27 V2 session plus direct review of `skills/paper-trader/paper_trader_v2.py`.

---

## What the live run proved

### Operational truth
- Main loop healthy
- Coinbase websocket healthy
- Scanner/trader/position manager cycling normally
- No global session kill-switch or cooldown was active

### Trading truth
- The system could recover after early losses, so the machine itself is functional
- But later in the run it went ~30+ minutes with **0 accepted candidates** despite repeated strong names on the board

### Candidate-eval truth
Recent 40-minute rejection sample:
- `leader_exhausted`: 69
- `cooldown`: 20
- `needs_reset`: 13
- `stale_reentry_after_no_move`: 9
- `insufficient_persistence`: 4
- `effective_score_below_regime_threshold`: 4
- accepts: **0**

This means the no-trade stretch was not caused by market emptiness. It was caused mainly by lifecycle suppression.

---

## Code areas responsible

## 1. `_reentry_decision(...)`
Location: `skills/paper-trader/paper_trader_v2.py`

This function blocks reused symbols based on:
- `blocked_until`
- `lifecycle`
- reclaim thresholds
- prior exit reason

### Current behavior
- `lifecycle in {'active', 'leader_active'}` => reject `cooldown`
- `lifecycle == 'needs_reset'` => reject `needs_reset`
- `lifecycle in {'choppy', 'exhausted'}` => reject `leader_exhausted`
- blocked symbols only escape via strict reclaim conditions (`strong_reclaim`, `exceptional_reclaim`, `no_move_reclaim`)

### Problem
The escape hatch is too strict for genuinely repaired names.
In practice, symbols like TRIA were repeatedly blocked as `cooldown` even with:
- high score
- strong drift
- strong persistence
- fresh tape

The current reclaim path requires too much “perfect proof” before forgiveness.

---

## 2. `_set_symbol_reentry_state(...)`
This function sets:
- lifecycle
- `reentry_blocked_until`
- last exit reason / pnl / peak pnl

### Problem
The durations and lifecycle assignments are too sticky relative to the speed of live rotation.
Current blocked windows can extend 25–45+ minutes depending on the exit pattern.
That may be reasonable for bad names, but it is too slow for fast repaired leaders in a live momentum tape.

---

## 3. `_symbol_churn_profile(...)`
This function calculates:
- `weak_exit_count`
- `recent_repeat_count`
- exhaustion penalties
- `exhausted` boolean

### Problem
The exhaustion classification is useful, but too eager to keep names suppressed after the tape has clearly changed.
Repeated prior interaction can dominate current live strength too heavily.

---

## 4. `_build_shortlist(...)`
This is where all gating stacks together:
- re-entry decision
- exhaustion rejection
- effective score penalties
- tight regime thresholds
- structure / confidence checks

### Problem
The composition of all filters creates cumulative lockout.
Each individual filter is defensible, but together they are too punitive on recently traded leaders.

---

## What should change

## A. Replace binary suppression with staged forgiveness
Current behavior is too binary:
- trusted before failure
- heavily distrusted after failure
- only allowed back on very strict reclaim proof

### Proposed change
Add **graduated recovery states**:
- `needs_reset`
- `watch_reclaim`
- `recovered`
- `exhausted`

Meaning:
- `needs_reset`: still cooling off
- `watch_reclaim`: not fully trusted, but can re-enter on stronger-than-baseline reclaim
- `recovered`: prior failure no longer dominates current state
- `exhausted`: still strongest suppression tier

This gives the model a middle lane between “hard block” and “fully clear.”

---

## B. Add a faster forgiveness path for repaired leaders
### Proposed override
Allow re-entry if all are true:
- persistence >= 5
- freshness <= 30–45s
- drift_300s >= 0.30
- drift_900s >= 0.20
- score >= 0.62–0.68
- current move is stronger than the move at prior failed exit

This should apply especially after:
- `fake_pump_confirmed`
- `no_move`
- `timeout`

Not after large stop-loss failures unless the reclaim is exceptional.

### Why
This would have likely reopened names like TRIA or ANKR sooner when they showed renewed strength, without reopening obvious churn garbage.

---

## C. Separate stop-loss aftermath from fake-pump / no-move aftermath
Current lifecycle logic does not sufficiently distinguish between:
- a name that truly failed hard
- a name that simply produced a weak first attempt

### Proposed treatment
#### After `stop_loss`
- keep stronger restriction
- require deeper reset or exceptional reclaim

#### After `fake_pump_confirmed`
- allow earlier re-entry if fresh strength returns quickly
- use shorter block + stronger drift test

#### After `no_move` / `timeout`
- shorter block window
- permit re-entry once drift / freshness clearly repair

This makes punishment proportional to the nature of failure.

---

## D. Reduce `leader_exhausted` stickiness
This is the biggest live problem.
Names like ANKR were repeatedly rejected as `leader_exhausted` even while posting very strong live metrics.

### Proposed rule
`leader_exhausted` should expire or soften when:
- no fresh weak exit has occurred for N minutes
- score is above a reclaim threshold
- freshness is strong
- drift_300s and drift_900s both exceed reclaim thresholds

Instead of a hard `False`, downgrade to:
- `watch_reclaim`
- or a heavier score penalty rather than outright reject

This preserves caution without forcing empty loops.

---

## E. Cap repeated same-name reopens per rolling window
Part of the current design tries to prevent same-name addiction by suppressing leaders after reuse.
A cleaner way to do this is to directly limit repeat opens instead of using overly broad lifecycle suppression.

### Proposed rule
Per symbol, per rolling 60–90 minutes:
- max 2 full opens unless reclaim score exceeds override threshold

This handles churn explicitly and may allow softer lifecycle rules elsewhere.

---

## F. Tighten quality on *new* entries while loosening repaired re-entry logic
The current problem is not just suppression. It is also that winners are too small.
So the fix should not be “let everything trade more.”

### Proposed combined approach
- **new symbols:** slightly stricter entry quality
- **repaired proven leaders:** easier re-entry when reclaim is real

This shifts the bot from:
- broad participation
- harsh repeat suppression

to:
- better first entries
- smarter second-chance entries

---

## Concrete code changes to make

## 1. `_reentry_decision(...)`
### Add new intermediate state logic
- if lifecycle is `leader_active` or `exhausted`, do not hard reject immediately
- first evaluate a new `fast_reclaim_ok(...)`
- only hard reject if reclaim conditions fail clearly

### New helper idea
```python
def _fast_reclaim_ok(candidate, ticker, entry):
    score = float(candidate.get('score') or 0.0)
    persistence = int(candidate.get('persistence') or 0)
    drift_300s = float(ticker.get('drift_300s') or 0.0)
    drift_900s = float(ticker.get('drift_900s') or 0.0)
    freshness = float(ticker.get('freshness_seconds') or 9999.0)
    momentum = float(candidate.get('momentum') or 0.0)
    return (
        persistence >= 5 and
        score >= 0.64 and
        freshness <= 45 and
        drift_300s >= 0.30 and
        drift_900s >= 0.20 and
        momentum >= 4.0
    )
```

Then use exit-reason-specific thresholds.

---

## 2. `_set_symbol_reentry_state(...)`
### Shorten and differentiate blocked windows
Suggested starting point:
- `stop_loss`: 35–45m
- `fake_pump_confirmed`: 10–20m
- `no_move`: 10–15m
- `timeout`: 10–15m
- weak continuation fail: 15–20m

Current windows appear too uniform / too long for live repaired names.

---

## 3. `_symbol_churn_profile(...)`
### Keep exhaustion penalty, but stop letting it dominate forever
Suggested:
- decay recent repeat penalties faster
- reduce penalty if symbol posts strong reclaim metrics later
- do not let `recent_repeat_count` alone keep a name in effective prison

---

## 4. `_build_shortlist(...)`
### Change rejection order
Currently hard re-entry rejection happens early.
Instead:
- compute reclaim score first
- if reclaim score is very strong, downgrade certain lifecycle blocks into score penalties
- only hard reject when reclaim is weak

This will stop the system from auto-skipping names that are actually the best thing moving.

---

## Research-backed interpretation of the run

### What should *not* be changed
- keep anti-revenge logic
- keep anti-churn intent
- keep fake-pump defense
- keep no-move cleanup
- keep hard skepticism after large stop-loss failures

### What *should* change
- faster forgiveness after small/repairable failures
- less sticky `leader_exhausted`
- more nuanced reclaim overrides
- more proportional cooldown duration
- shift from hard blocks to graded penalties where possible

---

## Expected outcome if fixed correctly

### Desired behavior
- fewer 30+ minute empty loops while strong names are still moving
- fewer repeated rejects on repaired leaders like TRIA / ANKR / FET
- same-name churn still contained
- more participation when the board repairs
- better chance of capturing second-leg moves

### Risk if overdone
If forgiveness becomes too easy:
- churn returns
- same-name addiction returns
- fake second legs get re-bought too often

So the target is not “trade more.”
The target is:
**trade repaired names sooner, but only when the reclaim is objectively stronger than the failed attempt.**

---

## Final summary
The run shows the post-trade suppression layer is now over-weighted.
It is preventing some of the old failure modes, but it is also creating self-inflicted inactivity by locking out the active universe after initial interaction.

The fix is not to remove cooldowns.
The fix is to replace blunt suppression with:
- proportional cooldowns
- faster reclaim overrides
- graded recovery states
- and a more forgiving path for genuinely repaired leaders.
