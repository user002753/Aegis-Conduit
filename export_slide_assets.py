#!/usr/bin/env python3
"""Export slide-ready CSV and PNG assets from anomaly history.

Usage examples:
  python export_slide_assets.py
  python export_slide_assets.py --json .cache/anomaly_history.json --out-dir .cache --csv --png

The script reads a JSON array of anomaly records (default: .cache/anomaly_history.json),
writes a CSV and produces a combined PNG suitable for slides: line chart of anomaly
scores over time and a bar chart of top sources by average anomaly score.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from collections import defaultdict
from datetime import datetime
from typing import List, Dict, Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def load_history(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"History file not found: {path}")
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError("Expected JSON array of records")
    return data


def write_csv(records: List[Dict[str, Any]], out_csv: str) -> None:
    if not records:
        print("No records to write to CSV")
        return
    # collect all field names across records for a broad CSV
    fieldnames = sorted({k for r in records for k in r.keys()})
    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            writer.writerow({k: r.get(k, "") for k in fieldnames})
    print(f"Wrote CSV: {out_csv}")


def make_slide_png(records: List[Dict[str, Any]], out_png: str) -> None:
    if not records:
        print("No records to plot")
        return
    times = []
    scores = []
    by_source = defaultdict(list)
    for r in records:
        ts = None
        if "timestamp" in r and r["timestamp"]:
            raw = r["timestamp"]
            try:
                ts = datetime.fromisoformat(raw)
            except Exception:
                try:
                    ts = datetime.fromtimestamp(float(raw))
                except Exception:
                    ts = None
        elif "time" in r:
            try:
                ts = datetime.fromisoformat(r["time"]) 
            except Exception:
                ts = None
        times.append(ts)

        # try common anomaly score keys
        score = None
        for k in ("anomaly_score", "score", "anomaly", "value"):
            if k in r and r[k] is not None:
                try:
                    score = float(r[k])
                    break
                except Exception:
                    score = 0.0
        if score is None:
            score = 0.0
        scores.append(score)

        src = r.get("source") or r.get("origin") or r.get("node") or "unknown"
        by_source[src].append(score)

    # pairs with valid times for the time-series plot
    paired = [(t, s) for t, s in zip(times, scores) if t is not None]
    paired.sort()
    times_sorted = [p[0] for p in paired]
    scores_sorted = [p[1] for p in paired]

    fig, axs = plt.subplots(1, 2, figsize=(11, 5))

    # Left: time series
    if times_sorted:
        axs[0].plot(times_sorted, scores_sorted, marker="o", linewidth=1)
        axs[0].set_title("Anomaly score over time")
        axs[0].set_xlabel("Time")
        axs[0].set_ylabel("Anomaly score")
        axs[0].grid(True, linestyle="--", alpha=0.4)
    else:
        axs[0].text(0.5, 0.5, "No timestamped records", ha="center", va="center")

    # Right: top sources by average anomaly
    avg_by_source = {k: (sum(v) / len(v) if v else 0.0) for k, v in by_source.items()}
    top = sorted(avg_by_source.items(), key=lambda x: x[1], reverse=True)[:8]
    if top:
        labels = [t[0] for t in top][::-1]
        values = [t[1] for t in top][::-1]
        axs[1].barh(labels, values, color="#d9534f")
        axs[1].set_title("Top sources (avg anomaly)")
        axs[1].set_xlabel("Avg anomaly score")
    else:
        axs[1].text(0.5, 0.5, "No source data", ha="center", va="center")

    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    print(f"Wrote PNG: {out_png}")


def normalize_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized = []
    for r in records:
        nr = dict(r)
        if "timestamp" not in nr:
            if "time" in nr:
                nr["timestamp"] = nr.pop("time")
            elif "received_at" in nr:
                nr["timestamp"] = nr["received_at"]
            else:
                nr["timestamp"] = None
        if "anomaly_score" not in nr:
            if "score" in nr:
                nr["anomaly_score"] = nr["score"]
            elif "anomaly" in nr:
                nr["anomaly_score"] = nr["anomaly"]
        normalized.append(nr)
    return normalized


def main() -> None:
    parser = argparse.ArgumentParser(description="Export CSV and PNG from anomaly history for slides")
    parser.add_argument("--json", "-j", default=".cache/anomaly_history.json", help="input JSON history file")
    parser.add_argument("--out-dir", "-o", default=".cache", help="output directory")
    parser.add_argument("--csv", action="store_true", help="write CSV file only")
    parser.add_argument("--png", action="store_true", help="write PNG file only")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    try:
        records = load_history(args.json)
    except Exception as exc:
        print(f"Error loading history: {exc}")
        return

    records = normalize_records(records)

    if args.csv:
        out_csv = os.path.join(args.out_dir, "anomaly_history.csv")
        write_csv(records, out_csv)
        return

    if args.png:
        out_png = os.path.join(args.out_dir, "anomaly_slide.png")
        make_slide_png(records, out_png)
        return

    # default: write both
    out_csv = os.path.join(args.out_dir, "anomaly_history.csv")
    write_csv(records, out_csv)
    out_png = os.path.join(args.out_dir, "anomaly_slide.png")
    make_slide_png(records, out_png)


if __name__ == "__main__":
    main()
