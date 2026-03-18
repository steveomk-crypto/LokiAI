#!/usr/bin/env python3
"""Walk-forward evaluator for market_scanner heuristics.

Usage:
    python3 scripts/scanner_walkforward.py --window 12 --min-runs 20

The harness loads existing market_logs JSONL files, builds chronological
runs, and then walks forward run-by-run. For each step it uses the prior
`window` runs as training data to derive median thresholds for key
scanner metrics (score, momentum, liquidity_score, alignment). It then
compares the next run against those medians and records how many
"strong" signals would have satisfied the historical medians.

Output is appended to system_logs/scanner_walkforward.jsonl so we can
track heuristic drift over time.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import median
from typing import Dict, List, Tuple

LOG_DIR = Path("/data/.openclaw/workspace/market_logs")
OUTPUT_PATH = Path("/data/.openclaw/workspace/system_logs/scanner_walkforward.jsonl")
DEFAULT_WINDOW = 12
DEFAULT_MIN_RUNS = 20


def _load_runs() -> List[Dict]:
    runs: List[Dict] = []
    if not LOG_DIR.exists():
        return runs
    for path in sorted(LOG_DIR.glob("*.jsonl")):
        by_timestamp: Dict[str, List[Dict]] = {}
        with path.open("r", encoding="utf-8") as handle:
            for raw in handle:
                line = raw.strip()
                if not line or not line.startswith("{"):
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = entry.get("timestamp")
                if not ts:
                    continue
                by_timestamp.setdefault(ts, []).append(entry)
        for ts in sorted(by_timestamp.keys()):
            runs.append({
                "timestamp": ts,
                "entries": by_timestamp[ts]
            })
    runs.sort(key=lambda item: item["timestamp"])
    return runs


def _extract_metric(entries: List[Dict], field: str) -> List[float]:
    values: List[float] = []
    for entry in entries:
        value = entry.get(field)
        if value is None:
            continue
        try:
            values.append(float(value))
        except (TypeError, ValueError):
            continue
    return values


def _summarize_training(entries: List[Dict]) -> Dict[str, float]:
    summary = {}
    for field in ("score", "momentum", "liquidity_score", "momentum_alignment_score"):
        data = _extract_metric(entries, field)
        summary[f"median_{field}"] = median(data) if data else 0.0
    summary["median_persistence"] = median(_extract_metric(entries, "persistence")) if entries else 0.0
    return summary


def _evaluate_run(test_entries: List[Dict], medians: Dict[str, float]) -> Dict[str, float]:
    strong = 0
    tier_a_ready = 0
    for entry in test_entries:
        score = float(entry.get("score") or 0.0)
        momentum = float(entry.get("momentum") or 0.0)
        liquidity_score = float(entry.get("liquidity_score") or 0.0)
        alignment_score = float(entry.get("momentum_alignment_score") or 0.0)
        if (score >= medians.get("median_score", 0.0) and
                momentum >= medians.get("median_momentum", 0.0)):
            strong += 1
            if liquidity_score >= medians.get("median_liquidity_score", 0.0) and alignment_score >= medians.get("median_momentum_alignment_score", 0.0):
                tier_a_ready += 1
    total = len(test_entries)
    return {
        "entries": total,
        "strong_signals": strong,
        "tier_a_ready": tier_a_ready,
        "strong_ratio": (strong / total) if total else 0.0,
        "tier_a_ready_ratio": (tier_a_ready / total) if total else 0.0,
    }


def run_walkforward(window: int, min_runs: int) -> List[Dict]:
    runs = _load_runs()
    if len(runs) < max(window + 1, min_runs):
        return []
    results: List[Dict] = []
    for idx in range(window, len(runs)):
        train_slice = runs[idx - window: idx]
        test_run = runs[idx]
        training_entries = [entry for run in train_slice for entry in run["entries"]]
        medians = _summarize_training(training_entries)
        eval_stats = _evaluate_run(test_run["entries"], medians)
        results.append({
            "timestamp": test_run["timestamp"],
            "training_start": train_slice[0]["timestamp"],
            "training_end": train_slice[-1]["timestamp"],
            **medians,
            **eval_stats
        })
    return results


def write_results(rows: List[Dict]) -> None:
    if not rows:
        return
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Walk-forward analyzer for market_scanner heuristics")
    parser.add_argument("--window", type=int, default=DEFAULT_WINDOW, help="Number of prior runs used for training")
    parser.add_argument("--min-runs", type=int, default=DEFAULT_MIN_RUNS, help="Minimum runs required before evaluation")
    parser.add_argument("--dry-run", action="store_true", help="Print results instead of writing to log")
    args = parser.parse_args()

    rows = run_walkforward(window=args.window, min_runs=args.min_runs)
    if not rows:
        print("Insufficient market_logs data for walk-forward analysis.")
        return
    if args.dry_run:
        print(json.dumps(rows[-1], indent=2))
    else:
        write_results(rows)
        print(f"Appended {len(rows)} walk-forward rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
