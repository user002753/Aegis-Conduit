#!/usr/bin/env python3
"""Small analysis utility for anomaly history.

Reads `.cache/anomaly_history.json` (or a provided JSON file) and prints
summary statistics suitable for slides: count, mean/median/std, top sources,
time range, and anomaly rate above a threshold. Optionally writes a summary
JSON file.
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


def load_history(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"History file not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data


def parse_iso(ts: str) -> datetime:
    # our records end with Z; strip and use fromisoformat
    if ts.endswith("Z"):
        ts = ts[:-1]
    return datetime.fromisoformat(ts)


def summarize(history: List[Dict[str, Any]], threshold: float = 0.8) -> Dict[str, Any]:
    n = len(history)
    scores = [float(h.get("score", 0.0)) for h in history]
    sources = [h.get("source") for h in history if h.get("source")]
    cnt = Counter(sources)
    top_sources = cnt.most_common(10)
    top_anomalous = [h for h in history if float(h.get("score", 0.0)) >= threshold]
    times = [parse_iso(h["ts"]) for h in history if h.get("ts")]

    return {
        "count": n,
        "mean_score": statistics.mean(scores) if scores else 0.0,
        "median_score": statistics.median(scores) if scores else 0.0,
        "stdev_score": statistics.pstdev(scores) if scores else 0.0,
        "top_sources": top_sources,
        "anomalous_count": len(top_anomalous),
        "anomalous_rate": len(top_anomalous) / n if n else 0.0,
        "time_range": {
            "start": min(times).isoformat() if times else None,
            "end": max(times).isoformat() if times else None,
        },
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Analyze anomaly_history.json and produce summary stats.")
    p.add_argument("--file", "-f", default=".cache/anomaly_history.json", help="Path to anomaly history JSON")
    p.add_argument("--threshold", "-t", type=float, default=0.8, help="Anomaly threshold to compute anomalous rate")
    p.add_argument("--out", "-o", help="Optional path to write JSON summary")
    args = p.parse_args()

    path = Path(args.file)
    try:
        history = load_history(path)
    except Exception as e:
        print(f"Error loading history: {e}")
        raise

    summary = summarize(history, threshold=args.threshold)

    # Print human-friendly summary
    print("Anomaly History Summary")
    print("-----------------------")
    print(f"Total records: {summary['count']}")
    print(f"Mean score: {summary['mean_score']:.3f}")
    print(f"Median score: {summary['median_score']:.3f}")
    print(f"Std (population): {summary['stdev_score']:.3f}")
    print(f"Anomalous (>= {args.threshold}): {summary['anomalous_count']} ({summary['anomalous_rate']*100:.1f}%)")
    print("Top sources:")
    for src, c in summary["top_sources"]:
        print(f"  - {src}: {c}")
    if summary["time_range"]["start"]:
        print(f"Time range: {summary['time_range']['start']} -> {summary['time_range']['end']}")

    if args.out:
        out_path = Path(args.out)
        with out_path.open("w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=2)
        print(f"Wrote summary to {out_path}")


if __name__ == "__main__":
    main()
