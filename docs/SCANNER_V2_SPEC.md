# Scanner V2 Spec

## Purpose
Scanner V2 exists to answer a more useful question than "what is moving?" The system should identify what is realistically actionable for a small Coinbase account while still tracking broader market context from DEX and other venues. The current bankroll constraint is approximately **$41 on Coinbase**, and the account is funded for discovery and future deployment only. No live money is touched until the broader system is stable.

## Core Objective
Turn raw market data into a ranked set of:
1. **Coinbase-actionable candidates** for future live deployment
2. **Paper-trade candidates** for the current system
3. **DEX-context candidates** that are useful for sentiment, rotation detection, and product/content generation
4. **Watch-only / avoid names** that should not distract execution

## Design Principle
Scanner V2 is not a hype detector. It is a selection engine for realistic, tradable opportunity. The system should prefer fewer, cleaner setups over noisy broad coverage.

## Venue Model
### Primary execution venue
- **Coinbase**
- Coinbase-listed spot assets should be treated as the highest-value execution universe because they map directly to the funded account.

### Secondary context venues
- **DEX / DexScreener** for early rotation, emerging momentum, and product/content context
- **CoinGecko / Coinpaprika / Binance / OKX** as supporting market context and comparative volume/momentum sources

## Account Constraint
The current funded Coinbase account has approximately **$41**. This means the scanner must optimize for:
- names actually listed on Coinbase
- enough liquidity to enter/exit without nonsense
- enough expected move to matter after friction
- setups clean enough that a tiny account is not just donating fees to noise
- realistic patience: sometimes the correct output is "wait"

## Scanner Outputs
### 1. Coinbase-actionable
Names that are actually worth monitoring for future deployment once the system is stable.

Required characteristics:
- listed on Coinbase
- positive momentum with strengthening behavior
- enough volume/liquidity for clean small-size execution
- not obviously extended or collapsing
- expected move large enough to matter for a tiny account

### 2. Paper-trade candidates
Names suitable for the current paper trading system, even if the future live deployment rules become stricter.

Required characteristics:
- score above threshold
- pass persistence / quality filters
- fit current risk framework

### 3. DEX-context candidates
Names not necessarily tradable through Coinbase, but still useful for:
- spotting sector rotation
- identifying sentiment beacons
- building Substack/Gumroad commentary
- front-running attention shifts before CEX participation

### 4. Avoid / watch-only
Names that should not clutter execution attention.

Examples:
- isolated spikes
- low-liquidity noise
- untradeable small-cap chaos
- already-fading moves
- momentum without persistence

## Proposed Ranking Logic
### Primary ranking pillars
1. **Coinbase tradability**
   - hard preference for assets listed on Coinbase
   - boost for USD/USDC/USDT-accessible spot pairs

2. **Persistence quality**
   - repeated strength across scans matters more than one-scan spikes
   - higher persistence should strongly improve rank

3. **Momentum quality**
   - prefer accelerating or steady continuation over isolated vertical candles
   - penalize fading / isolated spike behavior

4. **Volume quality**
   - strong real volume, not just price percentage moves
   - prefer names with sustained trade activity

5. **Execution realism**
   - the move has to be meaningful enough for tiny capital
   - names with dead ranges or ugly friction should rank lower

6. **DEX context signal**
   - DEX momentum can provide context, but should not override Coinbase execution realism

## Hard Rejects
Scanner V2 should be able to reject names automatically when they are:
- not realistically tradeable for the intended venue
- too illiquid
- too noisy / scammy
- isolated spikes with weak persistence
- fading after the move already happened
- poor fit for a tiny account where even success would not overcome friction

## Classification Layer
Every top-ranked name should ideally be labeled with an execution posture:
- **scalp candidate**
- **intraday continuation**
- **short swing watch**
- **watch only**
- **avoid**

This matters because the account constraint is small and the system should avoid forcing the same playbook onto every setup.

## Dashboard / Product Relevance
Scanner V2 should feed:
- trader dashboard top opportunities
- paper trader candidate selection
- Telegram private alerts
- market broadcaster packets
- Substack/Gumroad outputs

The scanner should therefore produce both:
- execution-oriented ranking
- commentary/context-oriented ranking

## Relationship to Current Baseline
### Keep from current scanner
- momentum thresholding
- persistence logic
- repeated weak-signal rejection
- trend-shape scoring (accelerating / steady / isolated spike / fading)
- DEX sidecar ranking and wallet intel

### Add / change
- treat Coinbase as primary execution universe
- explicitly model small-account viability
- distinguish execution candidates from context candidates
- allow "wait" as a valid high-quality outcome
- reduce emphasis on broad market noise

## Current Priority
The immediate goal is not live deployment. The immediate goal is to restore and stabilize Scanner V2 so the system can:
1. generate better paper candidates
2. produce more relevant dashboard outputs
3. create more grounded content/products
4. prepare for eventual live deployment of the $41 Coinbase account once system stability is proven

## Implementation Plan
1. Fix pathing/runtime issues so the scanner reads/writes the correct workspace
2. Add Coinbase-actionable classification as a first-class concept
3. Split outputs into execution vs context buckets
4. Add small-account viability heuristics
5. Tune thresholds after observing fresh live scans
6. Reconnect scanner outputs to dashboard, trader, Telegram, and product generation

## Non-Goals For Now
- fully automated real-money execution
- over-optimizing for huge size / institutional liquidity
- chasing every micro-cap move
- maximizing signal count at the expense of quality

## Working Rule
If the scanner finds nothing worth doing, it should say so. Clean silence beats noisy false opportunity.
