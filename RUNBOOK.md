# Trading Pipeline Runbook

_Last updated: 2026-03-18_

## 1. Pipeline Overview

1. `market_scanner` – fetches CoinGecko snapshot + DexScreener pairs, writes ranked signals (`market_logs/YYYY-MM-DD.jsonl`).
2. `paper_trader` – opens $100 positions per top signals using risk_manager gating; logs open/closed trades.
3. `position_manager` – enforces partials, trailing stops, loser control, and the 3.5 h time-stop.
4. `market_broadcaster` – builds X-ready summary posts (`x_posts/post_*.txt`).
5. `telegram_sender` – pushes status updates to chat (cycle counter in `skills/telegram_sender/state.json`).
6. `performance_analyzer` – refreshes long-form reports.
7. `sol_paper_trader` – parallel Solana-only loop.
8. `market_cycle_daemon.sh` – cron-style wrapper that runs `run_market_cycle.sh` every 60 s.

## 2. Current Guardrails

- **Entry filters:** persistence ≥ 4 (scanner), risk_manager blocks anything with momentum < 4, volume < $120k, liquidity_score < 0.55, or liquidity_change_ratio < 1.1.
- **Risk sizing:** $100 per trade (≤1% of $10k account). Max 15 concurrent positions.
- **Profit capture:** 50% trim + trail armed at +3%, additional 25% trim at +6%, 3% trailing gap thereafter.
- **Exits:** loser control at –3%, time-stop at 3.5 h if |PnL| < 0.5%, standard TP/SL at ±8%/–4%.

## 3. Day-to-Day Ops

| Task | Command | Notes |
| --- | --- | --- |
| Manual cycle | `bash scripts/run_market_cycle.sh` | Runs lint + every task once.
| Start daemon | `nohup bash scripts/market_cycle_daemon.sh >/tmp/market_cycle_daemon.out 2>&1 &` | Logs to `system_logs/market_loop_cron.log` & writes PID file.
| Stop daemon | `pkill -f market_cycle_daemon.sh` (or kill PID from `system_logs/market_cycle_daemon.pid`) | Removes PID file via trap.
| Quick health | `PYTHONPATH=... python3 autonomous_market_loop.py --lint` | Verifies skill entrypoints.
| Analytics | `PYTHONPATH=... python3 skills/trade-analytics/scripts/run_attribute_breakdown.py` | Drops attribute report in `performance_reports/`.

## 4. Log / Data Map

- **System logs:** `system_logs/autonomous_market_loop.log`, `system_logs/market_loop_cron.log`.
- **Trades:** `paper_trades/open_positions.json`, `paper_trades/trades_log.json`, `paper_trades/position_actions.json`, `paper_trades/close_reports.jsonl`.
- **Performance docs:** `performance_reports/report_*.txt`, `performance_reports/attribute_breakdown_*.md`.
- **Market posts:** `x_posts/post_*.txt` + thread files.
- **Telegram state:** `skills/telegram_sender/state.json` (cycle count + last payload).

## 5. Pre-Flight Checklist

1. Confirm no daemon running (`ps -ef | grep market_cycle`).
2. Ensure `open_positions.json` is in the expected state (empty before a fresh session, or note current holdings).
3. Run lint (`autonomous_market_loop.py --lint`).
4. (Optional) Run the new trade analytics script to baseline current performance.
5. Kick `run_market_cycle.sh` once to confirm telemetry + comms.
6. Start the daemon.

## 6. Troubleshooting

- **Scanner returns 0 signals:** Check CoinGecko rate limit / connectivity (`cache/coingecko_snapshot.json` timestamp). Adjust `momentum_threshold` temporarily if market is flat.
- **Risk manager blocks everything:** Inspect latest `risk_logs/risk_decisions.json` to see which gate is tripping; most likely low liquidity_score or drawdown cap.
- **Telegram failures:** `skills/telegram_sender/state.json` contains the last error; update `secrets/telegram.env` if the chat ID/token rotated.
- **Daemon stuck:** Tail `system_logs/market_loop_cron.log`. A stuck lock file `/tmp/market_cycle.lock` can block new cycles—delete it if no `run_market_cycle.sh` is active.

## 7. Expansion Hooks

- **Analytics:** use `trade-analytics` skill output to update strategy_config when persistence buckets diverge.
- **Alerting:** upcoming addition will stream time-stop counts + loss streaks to Telegram (hook into `position_manager` and `risk_manager`).
- **Skill additions:** install new ClawHub skills or extend `trade-analytics` for liquidity cohorting when needed.

## 8. Dashboard Service

- Launch the UI with `scripts/run_dashboard.sh` (wrap with systemd or `nohup` for persistence).
- By default the script now runs NiceGUI on `0.0.0.0:8500`, so the dashboard stays reachable at `http://<server-ip>:8500` (existing firewall rule).
- To keep it private, override on launch: `HOST=127.0.0.1 PORT=8500 scripts/run_dashboard.sh` and tunnel with `ssh -N -L 18501:127.0.0.1:8500 <user>@<vps>` → `http://localhost:18501`.
- For a hardened public endpoint later, front 0.0.0.0:8500 with Caddy/Traefik + auth.
- NiceGUI assets hot-reload every 30s via the built-in timer; restart the service after code updates.
