#!/usr/bin/env python3
"""Demo runner: posts spoofed reports to the API to produce decision trace activity.

Usage:
    python scripts/demo_runner.py --host http://localhost:8000 --count 10 --interval 10

The script is intentionally conservative: it defaults to local host, small payloads,
and prints responses. It does not enable any external integrations.
"""
import argparse
import time
import json
import random

try:
    import requests
except Exception:
    requests = None


SAMPLE_REPORTS = [
    {"source": "observer-1", "type": "hazard", "location": [12.34, 56.78], "description": "bridge collapse suspected", "reference_id": "road_status_feed", "status": "authenticated"},
    {"source": "drone-a", "type": "supply", "location": [12.35, 56.79], "description": "package drop completed", "reference_id": "warehouse_inventories", "status": "verified"},
    {"source": "citizen-1", "type": "evac", "location": [12.36, 56.80], "description": "evacuation in progress", "reference_id": "evacuation_protocols", "status": "active"},
]


def post_report(host: str, payload: dict):
    url = host.rstrip("/") + "/report"
    if requests is None:
        print("requests library not available; cannot post to API")
        return None
    try:
        r = requests.post(url, json=payload, timeout=5.0)
        try:
            return r.json()
        except Exception:
            return {"status_code": r.status_code, "text": r.text}
    except Exception as e:
        return {"error": str(e)}


def fetch_traces(host: str):
    url = host.rstrip("/") + "/cot"
    if requests is None:
        return None
    try:
        r = requests.get(url, timeout=5.0)
        try:
            return r.json()
        except Exception:
            return {"status_code": r.status_code, "text": r.text}
    except Exception as e:
        return {"error": str(e)}


def run_demo(host: str, count: int, interval: int):
    print(f"Demo: posting {count} reports to {host} every {interval}s")
    for i in range(count):
        payload = random.choice(SAMPLE_REPORTS).copy()
        payload["demo_seq"] = i + 1
        payload["timestamp"] = int(time.time())
        print(f"Posting report {i+1}/{count}: {json.dumps(payload)}")
        res = post_report(host, payload)
        print("Response:", res)
        time.sleep(interval)

    print("Demo complete - fetching decision traces")
    traces = fetch_traces(host)
    print("Trace entries:", json.dumps(traces, indent=2))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="http://localhost:8000", help="API host base URL")
    p.add_argument("--count", type=int, default=6, help="Number of reports to post")
    p.add_argument("--interval", type=int, default=10, help="Seconds between posts")
    args = p.parse_args()

    run_demo(args.host, args.count, args.interval)


if __name__ == "__main__":
    main()
