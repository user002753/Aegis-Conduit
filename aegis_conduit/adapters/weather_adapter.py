"""Weather adapter supporting file-based and HTTP polling for hazard events.

The adapter keeps track of seen events to avoid duplicate delivery when
polling a file repeatedly. HTTP polling expects the endpoint to return JSON
with either a single event or a list of events.
"""

from __future__ import annotations

import json
from typing import Any, Iterable

import requests


class WeatherAdapter:
    def __init__(self) -> None:
        # track seen event fingerprints to avoid duplicates
        self._seen: set[str] = set()

    def _fingerprint(self, evt: Any) -> str:
        try:
            return json.dumps(evt, sort_keys=True)
        except Exception:
            return str(evt)

    def poll_file(self, path: str) -> list[dict[str, Any]]:
        """Read a newline-delimited JSON file and return new events.

        Each line may be a JSON object (event) or a JSON array of events.
        """
        out: list[dict[str, Any]] = []
        try:
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                    except Exception:
                        continue
                    if isinstance(payload, list):
                        items = payload
                    else:
                        items = [payload]

                    for it in items:
                        fp = self._fingerprint(it)
                        if fp in self._seen:
                            continue
                        self._seen.add(fp)
                        out.append(it)
        except FileNotFoundError:
            return []
        return out

    def fetch_http(self, url: str, timeout: float = 5.0) -> list[dict[str, Any]]:
        """Fetch events from an HTTP endpoint returning JSON.

        The endpoint may return a single object or a list of objects.
        """
        try:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            payload = resp.json()
        except Exception:
            return []

        out: list[dict[str, Any]] = []
        items = payload if isinstance(payload, list) else [payload]
        for it in items:
            fp = self._fingerprint(it)
            if fp in self._seen:
                continue
            self._seen.add(fp)
            out.append(it)
        return out
