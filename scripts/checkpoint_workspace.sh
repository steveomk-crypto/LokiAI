#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STAMP="$(date +"%Y-%m-%d %H:%M:%S")"
BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)"

printf '== Workspace checkpoint ==\n'
printf 'Root: %s\n' "$ROOT"
printf 'Branch: %s\n' "$BRANCH"
printf 'Time: %s\n\n' "$STAMP"

printf '== Git status before ==\n'
git status -sb || true
printf '\n'

# Add only safe paths. Secrets remain ignored by .gitignore.
git add \
  .gitignore \
  AGENTS.md \
  BOOT.md \
  BOOTSTRAP.md \
  HEARTBEAT.md \
  IDENTITY.md \
  MEMORY.md \
  RUNBOOK.md \
  SOUL.md \
  TOOLS.md \
  USER.md \
  docs \
  memory \
  artifacts \
  scripts \
  skills \
  dashboard \
  feeds \
  strategy \
  strategy_config.py \
  autonomous_market_loop.py \
  api_usage.py \
  atr_utils.py \
  ops_state.py \
  ops_state.yaml \
  market_scanner \
  trade_journal \
  performance_reports \
  paper_trades \
  sol_paper_trades \
  x_posts \
  queues \
  risk_logs \
  market_logs \
  system_logs \
  cache \
  2>/dev/null || true

if git diff --cached --quiet; then
  printf 'No staged changes. Nothing to commit.\n'
  exit 0
fi

MSG="checkpoint: ${STAMP}"
git commit -m "$MSG"

printf '\nCommitted: %s\n' "$MSG"
printf 'To publish: git push origin %s\n' "$BRANCH"
