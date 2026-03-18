#!/usr/bin/env python3
"""Lightweight pre-cycle validation for the market loop."""
from __future__ import annotations

import json
import sys
from pathlib import Path

WORKSPACE = Path("/data/.openclaw/workspace")
SYSTEM_LOG = WORKSPACE / "system_logs" / "autonomous_market_loop.log"
REQUIRED_SKILLS = {
    "market_scanner": WORKSPACE / "skills" / "market_scanner" / "market_scanner.py",
    "paper_trader": WORKSPACE / "skills" / "paper-trader" / "paper_trader.py",
    "position_manager": WORKSPACE / "skills" / "position-manager" / "position_manager.py",
    "market_broadcaster": WORKSPACE / "skills" / "market-broadcaster" / "market_broadcaster.py",
    "x_autoposter": WORKSPACE / "skills" / "x-autoposter" / "x_autoposter.py",
    "performance_analyzer": WORKSPACE / "skills" / "performance-analyzer" / "performance_analyzer.py",
    "sol_paper_trader": WORKSPACE / "skills" / "sol-paper-trader" / "sol_paper_trader.py",
}

SECRET_FILE = WORKSPACE / "secrets" / "x_api_credentials.env"
POSTS_DIR = WORKSPACE / "x_posts"


def check_required_skills() -> list[str]:
    missing = []
    for task, path in REQUIRED_SKILLS.items():
        if not path.exists():
            missing.append(f"{task}: missing entrypoint {path}")
    return missing


def check_error_loops(max_lines: int = 200, threshold: int = 3) -> list[str]:
    if not SYSTEM_LOG.exists():
        return []
    violations = []
    seen = set()
    try:
        with SYSTEM_LOG.open("r", encoding="utf-8") as handle:
            lines = handle.readlines()
    except OSError as exc:
        return [f"log_read: unable to read {SYSTEM_LOG}: {exc}"]

    lines = lines[-max_lines:]
    consecutive: dict[str, int] = {task: 0 for task in REQUIRED_SKILLS}
    for raw in reversed(lines):
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            continue
        task = entry.get("task")
        if task not in REQUIRED_SKILLS:
            continue
        status = entry.get("status")
        if status == "error":
            consecutive[task] += 1
            if consecutive[task] >= threshold and task not in seen:
                message = entry.get("message", "")
                violations.append(
                    f"{task}: {consecutive[task]} consecutive error entries (latest: {message})"
                )
                seen.add(task)
        else:
            consecutive[task] = 0
    return violations


def check_outbound_safety() -> list[str]:
    issues = []
    if not SECRET_FILE.exists() or not SECRET_FILE.read_text(encoding="utf-8").strip():
        issues.append("x_autoposter: secrets/x_api_credentials.env missing or empty")
    if not POSTS_DIR.exists():
        issues.append("market_broadcaster/x_autoposter: x_posts directory missing")
    return issues


def main() -> int:
    violations = []
    violations.extend(check_required_skills())
    violations.extend(check_error_loops())
    violations.extend(check_outbound_safety())

    if violations:
        for item in violations:
            print(f"VIOLATION: {item}")
        return 1
    print("Pre-cycle validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
