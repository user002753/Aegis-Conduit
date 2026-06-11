"""Persistent state store for Aegis Conduit using SQLite.

Provides simple persistence for `reports`, `trusted_events`, and `routes`.
This is intentionally lightweight for offline recovery in simulations and
edge deployments. Payloads are stored as JSON blobs.
"""

import json
import sqlite3
from typing import Any


class StateStore:
    def __init__(self, path: str | None = None) -> None:
        self.path = path or "aegis_state.db"
        self.conn: sqlite3.Connection | None = None

    def init_db(self) -> None:
        self.conn = sqlite3.connect(self.path)
        cur = self.conn.cursor()
        cur.execute(
            """CREATE TABLE IF NOT EXISTS reports (
                id TEXT PRIMARY KEY,
                payload TEXT
            )"""
        )
        cur.execute(
            """CREATE TABLE IF NOT EXISTS trusted_events (
                id TEXT PRIMARY KEY,
                payload TEXT
            )"""
        )
        cur.execute(
            """CREATE TABLE IF NOT EXISTS routes (
                id TEXT PRIMARY KEY,
                payload TEXT
            )"""
        )
        cur.execute(
            """CREATE TABLE IF NOT EXISTS cot_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT,
                entry_time TEXT,
                entry_text TEXT,
                signature TEXT
            )"""
        )
        self.conn.commit()

    def save_state(self, state: dict[str, Any]) -> None:
        if self.conn is None:
            self.init_db()
        cur = self.conn.cursor()

        cur.execute("DELETE FROM reports")
        cur.execute("DELETE FROM trusted_events")
        cur.execute("DELETE FROM routes")

        for r in state.get("reports", []):
            key = self._report_key(r)
            cur.execute(
                "INSERT OR REPLACE INTO reports (id, payload) VALUES (?, ?)",
                (key, json.dumps(r, default=str)),
            )

        for idx, e in enumerate(state.get("trusted_events", [])):
            cur.execute(
                "INSERT OR REPLACE INTO trusted_events (id, payload) VALUES (?, ?)",
                (str(idx), json.dumps(e, default=str)),
            )

        for route in state.get("routes", []):
            rid = route.get("route_id") or str(route)
            cur.execute(
                "INSERT OR REPLACE INTO routes (id, payload) VALUES (?, ?)",
                (rid, json.dumps(route, default=str)),
            )

        # optionally save CoT entries if present in state under 'cot_logs'
        for cot in state.get("cot_logs", []):
            try:
                cur.execute(
                    "INSERT INTO cot_logs (agent_id, entry_time, entry_text, signature) VALUES (?, ?, ?, ?)",
                    (cot.get("agent_id"), cot.get("time"), cot.get("text"), cot.get("signature")),
                )
            except Exception:
                # ignore individual failures
                pass

        self.conn.commit()

    def load_state(self) -> dict[str, Any]:
        if self.conn is None:
            self.init_db()
        cur = self.conn.cursor()

        cur.execute("SELECT payload FROM reports")
        reports = [json.loads(row[0]) for row in cur.fetchall()]

        cur.execute("SELECT payload FROM trusted_events")
        trusted_events = [json.loads(row[0]) for row in cur.fetchall()]

        cur.execute("SELECT payload FROM routes")
        routes = [json.loads(row[0]) for row in cur.fetchall()]

        cur.execute("SELECT agent_id, entry_time, entry_text, signature FROM cot_logs ORDER BY id ASC")
        cot_rows = [
            {"agent_id": r[0], "time": r[1], "text": r[2], "signature": r[3]} for r in cur.fetchall()
        ]

        return {"reports": reports, "trusted_events": trusted_events, "routes": routes, "cot_logs": cot_rows}

    def append_cot(self, agent_id: str, entry_time: str, entry_text: str, signature: str | None = None) -> None:
        if self.conn is None:
            self.init_db()
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO cot_logs (agent_id, entry_time, entry_text, signature) VALUES (?, ?, ?, ?)",
            (agent_id, entry_time, entry_text, signature),
        )
        self.conn.commit()

    def get_cot(self, limit: int | None = None) -> list[dict[str, str]]:
        if self.conn is None:
            self.init_db()
        cur = self.conn.cursor()
        q = "SELECT agent_id, entry_time, entry_text, signature FROM cot_logs ORDER BY id ASC"
        if limit:
            q += f" LIMIT {int(limit)}"
        cur.execute(q)
        return [{"agent_id": r[0], "time": r[1], "text": r[2], "signature": r[3]} for r in cur.fetchall()]

    def close(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None

    def _report_key(self, report: dict[str, Any]) -> str:
        evt = report.get("event", {})
        ref = evt.get("reference_id") or evt.get("type") or str(evt)
        return f"{report.get('source')}|{report.get('timestamp')}|{ref}"
