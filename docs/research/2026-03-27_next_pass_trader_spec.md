# Next Pass Trader Spec — 2026-03-27

## Context
The post-reset 4-hour run was a meaningful improvement over prior behavior:
- 37 closed trades
- +1.3005% net PnL
- positive expectancy (+0.0351% / trade)
- max sequence drawdown only -1.1481%
- no major dead-window freeze

This confirms the suppression fix improved runtime behavior and reduced self-inflicted inactivity.

However, the run also surfaced the next layer of problems:
- high-confidence trades underperformed
- edge remains thin
- lots of outcomes are near-flat
- `leader_exhausted` still appears too often in candidate rejections

This document proposes the next research / implementation pass.

---

## What the run proved

### 1. The machine is now operationally healthy
- Loop stable
- Feed stable
- Entry/exit cycle functioning
- Positive expectancy achieved without heroic drawdown

### 2. The suppression fix helped
- The bot traded through the session
- It no longer sat dead for massive stretches in the same obvious way
- It could re-engage after reset and produce a healthier profile

### 3. The edge is still fragile
Positive expectancy exists, but only barely.
This is not yet “production-safe confidence.”

---

## Main problems to solve next

## A. High-confidence lane is miscalibrated
### Evidence
Run breakdown:
- **High confidence**: 17 trades, -1.0676% net, 35.29% win rate
- **Standard confidence**: 20 trades, +2.3681% net, 55.0% win rate

### Interpretation
The current high-confidence label is too generous or too momentum-biased.
It appears to be selecting setups that look impressive structurally but do not monetize better than the standard lane.

### Goal
Make “high confidence” genuinely rarer and more predictive.

### Suggested changes
1. Raise high-confidence score threshold modestly
2. Require stronger structure persistence for high-confidence continuation
3. Penalize names that are only strong because of short-horizon drift spikes
4. Require higher follow-through quality after a prior fake-pump pattern
5. Audit whether high-confidence names are simply too extended at entry

---

## B. Increase winner expansion slightly without giving back discipline
### Evidence
The run was green mostly because losses shrank, not because winners expanded dramatically.
Average win remains modest.
Median trade remains near zero.

### Goal
Let the machine keep more of the better trades while preserving strong cleanup on weak ones.

### Suggested changes
1. For high-confidence names only, consider delaying first de-risk slightly when structure remains constructive
2. Separate fake-pump detection from healthy momentum continuation more cleanly
3. Add a “hold-through-strength” clause if:
   - drift_300s remains positive after first trim
   - drift_900s remains constructive
   - freshness remains live
   - no sharp giveback appears
4. Preserve no-move cleanup for mediocre names

### Constraint
Do **not** revert to loose hold-and-hope behavior.
The point is to expand winners selectively, not globally loosen exits.

---

## C. Reduce false `leader_exhausted` persistence further
### Evidence
Even in the improved run, candidate evals still showed repeated `leader_exhausted` rejects on active names.
This no longer froze the machine completely, but it still appears heavier than ideal.

### Goal
Keep anti-churn behavior, but further reduce false lockout on names that are visibly still tradable.

### Suggested changes
1. Add decay to `leader_exhausted` state after N cycles without a fresh weak exit
2. Allow downgrade from `exhausted` -> `watch_reclaim` after constructive drift + freshness combo
3. Make `leader_exhausted` depend partly on recent **failed** reuse, not just prior interaction history
4. Avoid hard reject if score is modest but structure is clearly rebuilding and recent repeat count is low

### Constraint
Do not fully remove the anti-recycling guard.
The old failure mode was real.

---

## D. Tighten entry quality for high-volatility fake-pump names
### Evidence
A lot of exits still come through:
- `fake_pump_confirmed`
- `no_move`

This is useful cleanup, but it also implies the bot still enters some names that were never likely to produce sustained continuation.

### Goal
Reduce low-payoff entries at the front door rather than relying entirely on exit cleanup.

### Suggested changes
1. Add a stricter pre-entry fake-pump screen for high-confidence names
2. Reject entries where drift is too explosive relative to score / persistence / momentum quality
3. Consider a stronger extension guard for names with huge 300s drift but weak 900s support
4. Add a mild penalty for names whose recent moves repeatedly convert into FP exits

---

## E. Differentiate confidence lanes by expected behavior, not just score
### Problem
Right now confidence appears to function mostly like a threshold label.
It should instead imply different management expectations.

### Suggested redesign
#### High confidence
- rarer entry
- stronger proof required
- slightly more room to hold if structure remains healthy
- should produce better average PnL than standard

#### Standard confidence
- more tactical
- quicker cleanup
- smaller expected payoff
- less trust in continuation

This would give each lane a coherent role instead of just two labels on similar behavior.

---

## F. Add post-run diagnostics as first-class outputs
### Goal
Make future analysis faster and less anecdotal.

### Suggested outputs after each run block (e.g. every 25 or 50 trades)
- confidence lane breakdown
- symbol reuse breakdown
- fake-pump rate by symbol and confidence
- no-move rate by symbol and confidence
- avg MFE / MAE if available
- average hold time by winner vs loser
- re-entry profitability vs first-entry profitability

This will make the next tuning pass much more evidence-driven.

---

## Recommended implementation order

## Phase 1 — Confidence calibration
1. Tighten high-confidence entry rules
2. Re-run and compare lane performance
3. Confirm high-confidence stops underperforming the standard lane

## Phase 2 — Winner expansion
1. Slightly improve hold logic on structurally healthy winners
2. Re-run and measure avg win change
3. Check if expectancy improves without drawdown spike

## Phase 3 — Exhaustion decay refinement
1. Soften `leader_exhausted` one more step
2. Track whether acceptance quality drops
3. Verify dead windows do not re-emerge and churn does not come back

## Phase 4 — Diagnostics layer
1. Add richer automated trade analytics
2. Save confidence / exit / symbol behavior summaries after each run

---

## Success criteria for next pass
A better next run should show most of the following:
- net PnL stays positive
- expectancy improves above +0.05% / trade
- max drawdown remains contained (< -2.0% sequence drawdown)
- high-confidence lane stops underperforming standard lane
- average win expands modestly
- `leader_exhausted` remains present but less dominant
- fewer trades end near exact flatline

---

## Final recommendation
The next priority is **not** another giant architecture rewrite.
The machine is past that stage.

The correct next pass is:
1. recalibrate high-confidence entries
2. improve selective winner expansion
3. further soften false exhaustion persistence
4. add better diagnostics so future tuning is faster and cleaner

In short:
**we are now optimizing edge quality, not reviving the machine.**
