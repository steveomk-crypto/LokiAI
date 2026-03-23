#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p backups
STAMP="$(date +"%Y-%m-%d_%H%M%S")"
OUT="backups/workspace-backup-${STAMP}.tar.gz"

printf 'Creating backup: %s\n' "$OUT"

# Keep secrets in the archive so local recovery is possible.
# Exclude heavy runtime noise and git metadata.
tar \
  --exclude='.git' \
  --exclude='winvenv' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='node_modules' \
  --exclude='backups/*.tar.gz' \
  -czf "$OUT" \
  .

printf 'Backup complete: %s\n' "$OUT"
ls -lh "$OUT"
