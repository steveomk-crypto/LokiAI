# Backup & Restore

## Goal
Make reinstall/reset events annoying instead of catastrophic.

## Source of Truth
### Versioned in GitHub
Safe-to-track workspace files:
- scripts/
- skills/
- dashboard/
- docs/
- memory/
- artifacts/
- runbooks/specs
- non-secret configs

### Local only (never commit)
- secrets/
- API keys / OAuth clients / wallets
- local PID files
- temporary caches and runtime-only noise

## Recovery Order
1. Restore/clone the Git repo into the workspace
2. Restore the local `secrets/` directory from secure backup
3. Restore latest workspace archive if Git is behind
4. Verify OpenClaw status: `openclaw status`
5. Verify dashboard / pipeline scripts still resolve paths
6. Re-run health checks and pipeline validation

## Backup Layers
### Layer 1: GitHub
Use Git for code, docs, specs, memory, and product artifacts that are safe to track.

### Layer 2: Local archive backups
Use `scripts/backup_workspace.sh` to create timestamped tarballs under `backups/`.

### Layer 3: Secret manifest + secure copy
Use `secrets/README.md` as the inventory of what must exist locally. Keep actual secret values outside Git.

## Recommended Workflow
### During work
- Use `scripts/checkpoint_workspace.sh` for safe Git checkpoints
- Use `scripts/backup_workspace.sh` before risky upgrades/reinstalls

### Before OpenClaw upgrades / reinstalls
1. Run workspace backup script
2. Confirm latest Git commit is pushed
3. Confirm `secrets/` exists in secure local storage
4. Only then update / reinstall

## Restore Checklist
- [ ] Repo restored
- [ ] Secrets restored
- [ ] Dashboard script checked
- [ ] OpenClaw gateway healthy
- [ ] Paper trader files present
- [ ] Artifacts/Gumroad/Substack docs restored
- [ ] Current operating spec restored
- [ ] Runbook restored

## Commands
### Safe checkpoint
`bash scripts/checkpoint_workspace.sh`

### Full backup archive
`bash scripts/backup_workspace.sh`

### Status check
`openclaw status`
