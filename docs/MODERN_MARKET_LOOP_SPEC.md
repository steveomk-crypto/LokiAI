# Modern Market Loop Spec

## Purpose
Define the current-generation ordered loop for the rebuilt LokiAI market machine.

This replaces reliance on the legacy autonomous loop chain for the new operating path.

## Ordered sequence
1. **Scanner**
   - refresh `cache/market_state.json`
   - update candidate context using current doctrine

2. **Social / Intel Pulse**
   - refresh `cache/social_intel_pulse.json`
   - synthesize scanner/news/telemetry context

3. **Paper Trader V2**
   - read fresh scanner state + Coinbase websocket ticker state
   - update V2 open positions, trades log, state, and audit summary

4. **Ops Alerts**
   - evaluate scanner/websocket/trader/service health
   - send Telegram Ops updates on meaningful state changes only

## Continuous service outside the loop
### Coinbase Websocket
The Coinbase Websocket is not a loop step. It is a continuously running service that keeps live market state warm for the loop.

## Outputs consumed by dashboards
The dashboards consume the resulting state files from:
- scanner
- websocket
- social/intel pulse
- paper trader v2

## Current runner
- `scripts/run_modern_market_loop.sh`

## Current goal
Establish a clean, ordered, current-generation loop without reactivating the legacy monolithic task chain.
