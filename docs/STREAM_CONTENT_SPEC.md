# Stream Content Spec

## Purpose
Lock the meaning of the stream dashboard now that the visual structure is stable.

This spec defines:
- what each stream panel is for
- what it should communicate to viewers
- what placeholder/manual content is acceptable for now
- what real data sources should feed it later
- what tone each panel should carry

The goal is to keep the current page structure stable while improving what the stream actually says.

## Core Principle
The stream dashboard is not an internal ops board. It is a **public-facing market intelligence scene**.

It should communicate:
- the machine is alive
- the machine is watching real markets
- the machine is disciplined
- the system is rebuilding honestly
- there are real outputs/products forming around it

It should not feel:
- scammy
- overhyped
- confusingly technical
- like a private debugging screen accidentally exposed

---

# 1. Top Strip

## Purpose
Immediate identity + liveness check.
A viewer should understand in a few seconds that:
- this is LokiAI
- the stream is live
- the scanner is working
- the websocket is online

## Current content
- `LokiAI Market Engine`
- `STREAM • LIVE`
- scanner signal count
- websocket online/offline

## Recommended final tone
Short, crisp, system-like.
No marketing language.

## Placeholder mode
Acceptable now.

## Future data source
- scanner state/status
- websocket state/status
- optional current operating mode config

## Notes
Keep this strip compact. It is a HUD, not a banner ad.

---

# 2. Left Rail — Live Movers

## Purpose
Show what is moving right now in the tracked Coinbase universe.

This is the stream’s immediate motion panel.
It tells viewers the system is watching a live market, not a static report.

## What it should communicate
- live pulse
- short-horizon movement
- current activity
- freshness

## Placeholder / current mode
The current live mover feed is acceptable as a real early version.
It is already connected to websocket data.

## Future improvements
- better movement labels (`building`, `fading`, `spiking`)
- cleaner selection logic
- stronger ranking based on live usefulness rather than just absolute drift

## Future data source
- `cache/coinbase_tickers.json`
- websocket-derived freshness metrics

## Tone
Fast, factual, clean.
No commentary inside the panel.

---

# 3. Left Rail — Scanner Highlights

## Purpose
Show the scanner’s structured judgment, not just live movement.

This panel answers:
- what the machine currently considers worth attention
- which names are surviving the quality gate

## What it should communicate
- ranked attention
- persistence
- trend character
- machine conviction

## Placeholder / current mode
Current panel is acceptable, but later the wording should become more public-readable.

## Future improvements
- replace shorthand like `p1` with clearer persistence language or a readable badge
- add cleaner trend tags
- eventually distinguish `Coinbase-actionable` from `context` if appropriate

## Future data source
- `cache/market_state.json`
- scanner ranking outputs

## Tone
Analytical, compact, signal-oriented.

---

# 4. Center Hero — Tactical Chart View

## Purpose
This is the visual heart of the stream.
It is the main windshield / tactical display.

This panel proves the stream is not just lists of tokens. It gives the system a real center of attention.

## What it should communicate
- a live or near-live market view
- active observation
- market structure, not just signal tables

## Current placeholder state
The current candle graphic placeholder is acceptable while the real chart source is being decided and wired.

## Decision to lock later
We need to decide:
- default symbol (`BTC-USD`, `ETH-USD`, or another anchor)
- timeframe
- whether the chart stays fixed or rotates

## Recommended initial behavior
- start with a stable anchor like `BTC-USD`
- fixed timeframe
- do not rotate aggressively at first

## Future data source
- real candle feed / chart data source for selected Coinbase symbol

## Tone
Heroic but clean. This panel is visual, not verbose.

---

# 5. Center Lower — Social / Intel Pulse

## Purpose
Provide a curated attention/catalyst layer that complements price and scanner data.

This is not a raw X feed.
This is a **curated market-relevant social/catalyst pulse**.

## What it should communicate
- important posts
- listing/drop chatter
- narrative shifts
- major catalyst events
- abnormal attention spikes

## Current placeholder state
Placeholder is correct and should remain lightweight until a structured feed exists.

## Future improvements
- use concise intel categories
- show source, topic, and freshness
- keep it curated and compact

## Future data source
Likely future files:
- `cache/social_pulse.json`
- `market_logs/social_pulse/YYYY-MM-DD.jsonl`

## Tone
Intel/comms tone. Short, serious, not social-media-casual.

---

# 6. Center Lower — Links / Support

## Purpose
Convert attention into action.
This is the stream’s soft monetization bridge.

## What it should communicate
- where to read more
- where to buy the product
- where to support/follow the mission

## Current placeholder state
Acceptable, but still primitive.

## Future improvements
This panel should eventually shift from raw destination listing to clearer calls to action such as:
- `Read the brief`
- `Get the pack`
- `Follow the build`
- `Support the mission`

## Future data source
Static config is fine at first.
Later could read from a dashboard config file.

## Tone
Direct, calm, confident.
Never spammy.

---

# 7. Right Rail — Operating / Mission Status

## Purpose
Trust layer.
This is where the stream tells the truth about what the system is and is not doing.

## What it should communicate
- paper-only status
- rebuild/stabilization mode
- funds staged but not yet deployed
- disciplined, risk-aware posture

## Why it matters
This is one of the strongest anti-scam panels on the page.
It shows the operator is not pretending the machine is fully finished or recklessly trading live.

## Current placeholder state
Current content is good.

## Future improvements
Make the wording slightly more polished over time, but keep the honesty intact.

## Future data source
- operating mode config
- paper/live mode state
- staged capital state if intentionally exposed

## Tone
Calm, direct, serious.

---

# 8. Right Rail — Latest Intelligence

## Purpose
Show that the machine produces outputs with value beyond raw charts.
This is the bridge from market observation to content/products.

## What it should communicate
- current brief/report/product output
- latest intelligence artifact
- evidence that the machine generates useful packaged work

## Current placeholder state
Current Atlas Pulse copy is acceptable.

## Future improvements
This panel should eventually pull automatically from:
- latest Substack brief
- latest Gumroad pack
- latest report headline

## Future data source
- docs/artifacts metadata
- future brief/product output metadata file

## Tone
Concise, credible, product-aware.

---

# 9. Global Tone Rules

## Stream-wide voice
- sharp
- calm
- data-driven
- futuristic
- no hype
- no cringe
- no fake urgency

## Messaging rules
- prefer short lines over long copy
- prefer facts over slogans
- prefer credibility over excitement
- let the visuals bring the excitement, not the language

---

# 10. Placeholder Policy

## Good placeholders
Placeholders are acceptable when they:
- reserve a future intelligence surface
- explain what will appear later
- do not pretend the system already has that feed

## Bad placeholders
Avoid placeholders that:
- fake precision
- imply live capability that does not exist
- use hype language to cover missing infrastructure

---

# 11. Public vs Private Boundary

## Safe for stream
- scanner summaries
- live mover summaries
- mission status
- intelligence/product headlines
- curated social/intel categories
- public links

## Keep out of stream
- raw logs
- private controls
- secrets
- internal debugging detail
- real-money control surfaces
- anything that could compromise security or trust

---

# 12. Immediate Next Step
Do not change the stream layout structure.
Instead, use this spec to tighten:
- panel titles
- panel copy
- future data source mapping
- public readability

This is the content layer that sits on top of the now-stable visual structure.
