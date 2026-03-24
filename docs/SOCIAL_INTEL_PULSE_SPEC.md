# Social / Intel Pulse Spec

## Purpose
Define the Social / Intel Pulse layer for LokiAI.

This is not a raw social feed.
This is a **curated catalyst and market-intelligence layer** designed to help:
- the Operator Dashboard
- the Stream Dashboard
- future Substack / Gumroad outputs
- daily market interpretation

The goal is to make the machine feel informed, not noisy.

---

# 1. Core principle

## Social / Intel Pulse should be:
- curated
- market-relevant
- catalyst-aware
- compact
- actionable when possible

## Social / Intel Pulse should NOT be:
- a tweet firehose
- vanity engagement bait
- random influencer chatter
- a scrolling sewer of low-value posts

If an item does not change interpretation, risk, narrative, or attention meaningfully, it should not be in the feed.

---

# 2. What goes into the feed

## A. Exchange / listing / market-structure catalysts
Examples:
- Coinbase listings / roadmap adds
- exchange delistings
- major product launches
- market-structure changes
- notable perp/spot expansion

## B. Macro / regulatory / ETF catalysts
Examples:
- ETF headlines
- SEC / regulatory developments
- rate / macro events with crypto relevance
- stablecoin policy developments

## C. Narrative rotation / sector heat
Examples:
- AI tokens bid
- DePIN catching flow
- L2 rotation
- meme exhaustion / quality rotation
- Coinbase-specific relative strength clusters

## D. High-signal social posts
Examples:
- major founder posts that change sentiment materially
- respected analysts/traders highlighting a catalyst
- project/team announcements with credible impact

Important:
A post must matter because of its market implication, not because it got likes.

## E. News summaries already available in local caches
Potential sources already present in workspace cache:
- CoinDesk
- CryptoCompare
- CoinGecko snapshot/news-related market context

---

# 3. What stays out

Do NOT include:
- random meme tweets
- generic “GM” / vibes posts
- low-follower noise
- repetitive calls with no new information
- market opinions with no catalyst
- spammy threads that say nothing
- duplicate items from multiple sources unless the duplication itself is meaningful

---

# 4. Item format

Each intel item should be normalized into a compact structure.

## Recommended fields
- `timestamp`
- `category` — exchange | macro | regulatory | narrative | social | project
- `headline`
- `source`
- `symbol_scope` — optional token(s) or sector(s)
- `importance` — low | medium | high
- `market_implication`
- `confidence` — low | medium | high
- `actionability` — observe | monitor | actionable

## Example
```json
{
  "timestamp": "2026-03-23T18:40:00Z",
  "category": "narrative",
  "headline": "AI basket regaining relative strength versus majors",
  "source": "internal synthesis",
  "symbol_scope": ["FET", "RNDR", "AKT"],
  "importance": "medium",
  "market_implication": "scanner candidates in AI cluster deserve closer confirmation checks",
  "confidence": "medium",
  "actionability": "monitor"
}
```

---

# 5. Panel behavior

## Stream Dashboard
The stream version should be:
- visual
- compact
- headline-driven
- readable at a glance

Recommended content:
- top 3 intel items
- category + headline
- one-line implication

Do NOT dump paragraphs or raw links.

## Operator Dashboard
The operator version can be slightly richer:
- top 5 items
- importance/confidence labels
- category grouping
- maybe token scope

---

# 6. Tone / presentation

The tone should be:
- calm
- sharp
- observational
- non-hype

Examples of good phrasing:
- `AI cluster showing renewed relative strength; worth monitoring for confirmed follow-through.`
- `Listing catalyst may increase attention, but confirmation still needed.`
- `Narrative heat rising, not yet enough to force allocation.`

Avoid:
- `THIS IS HUGE`
- `send it`
- `ape`
- overexcited market-tout language

---

# 7. First implementation version

## V1 goal
Build a **manual/semi-curated local intel layer** first.

That means:
- use existing local cache/news sources where available
- allow synthetic/internal summary items
- keep the data model simple
- feed the dashboards with a small normalized JSON file

## Suggested V1 artifact
- `cache/social_intel_pulse.json`

Containing something like:
```json
{
  "updated_at": "2026-03-23T18:45:00Z",
  "items": [ ... ]
}
```

---

# 8. Ranking logic

V1 ranking should favor:
1. direct Coinbase/exchange relevance
2. high-confidence macro/regulatory catalysts
3. narrative rotation with multiple supporting signals
4. strong social posts with real market implication

V1 should penalize:
- duplication
- stale items
- weak confidence
- low market implication

---

# 9. Relationship to trader/scanner

The Social / Intel Pulse is not a direct trade trigger by itself.

It should:
- inform operator judgment
- enrich stream context
- potentially support future scoring overlays

It should not automatically override scanner/trader rules in V1.

---

# 10. Immediate implementation recommendation

## Build V1 as:
1. a normalized JSON cache
2. a lightweight builder script
3. dashboard rendering for operator + stream

This keeps the social/intel layer useful without overengineering it.

---

# 11. Definition of success

Social / Intel Pulse is successful if it makes the machine feel:
- more aware
- more contextual
- more useful
- more alive

without making it feel noisy, spammy, or distracted.
