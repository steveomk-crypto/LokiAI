# LokiAI Operating Spec

## Mission
Build an autonomous system that turns market data into signals, trades, content, and digital products that generate income. This is not just a trading bot. It is a connected machine that combines trading, market intelligence, content creation, and product generation. The near-term goal is to prove a real trading edge. The long-term goal is to scale that edge into content, products, subscriptions, and eventually a paid intelligence system.

## Output Layer
### Daily outputs
- Market scans from DEX and Coinbase
- Ranked signal data
- Paper trades with full logging
- Position tracking
- Dashboard updates
- Private alerts through Telegram
- X posts
- Telegram updates
- Substack drafts/posts
- Gumroad-ready packs including signal breakdowns, strategy packs, and data exports

### Weekly outputs
- Performance reports
- PnL breakdowns
- Strategy reviews covering what worked and what failed

## Audience Ladder
1. Internal operator use first (LokiAI + user) to learn, refine, and prove profitability
2. Retail traders who want signals and direction without heavy thinking
3. Paid users such as Substack subscribers and Gumroad buyers
4. Longer term: paid community, tools, managed capital, and advanced products

## Revenue Model
Revenue is designed to stack across multiple layers:
1. Trading profits, once edge and risk control are proven
2. Content-driven income via Substack, X, and Telegram distribution
3. Digital product sales via Gumroad (strategy packs, signal data, exports)
4. Later layers: paid signal access, API access, consulting, affiliate/tool income

## Automation Boundaries
### Fully automated
- Market scans
- Signal ranking
- Data logging
- Paper trading
- Dashboard updates
- Private internal alerts

### Semi-automated (generate automatically, review before publish)
- X posts
- Telegram public updates
- Substack drafts/posts
- Product creation / packaging

### Manual only for now
- Real-money trades
- Pricing decisions
- Major strategy changes
- Critical API/account connections
- Anything that risks money or reputation

## Current Build State
### Already exists
- OpenClaw + LokiAI pipeline is running
- Market scanners, paper trading, and logging systems exist
- Telegram integration exists but is not fully stable
- Substack has one live post
- Gumroad has one live product
- NiceGUI dashboard exists but has stability/UI issues
- Coinbase websocket integration has been added but is still being stabilized
- Automation runs through a daemon loop instead of cron due to VPS limitations
- Some alert formatting issues still exist

### Incomplete / active work
- Consistent profitable trading
- Fully reliable automation pipeline
- Clean and stable dashboard UX
- Fully built paid subscription system
- Scalable product pipeline

## Priority Stack
1. Trading performance
2. System stability
3. Consistent output
4. Growth
5. Monetization scale

## Success Metrics
### Trading performance first
- PnL
- Win rate
- Drawdown control

### System health second
- Uptime
- Loop consistency
- Data accuracy

### Growth third
- Subscriber count
- Engagement
- Reach

### Revenue fourth
- Product sales
- Conversion rate
- Repeat buyers

## Brand Voice
- Sharp
- Calm
- Data-driven
- No hype
- No emotional language
- No scammy / influencer energy
- Observational and confident without being loud
- Straightforward reporting of signals, outcomes, and lessons
- Professional operator energy: execution and results over attention

## Working Principle
The system should behave like an operator running a machine, not a hype marketer. It should collect market data, turn it into usable intelligence, test and refine execution, then convert validated edge into distribution and products. Trading edge comes first. Monetization scales on top of proven signal quality.
