"""Digital twin / scenario simulator scaffolds.

Provides scenario templates and a simple runner for 'what-if' analysis.
"""
from __future__ import annotations

from typing import Dict, Any, List
import time


class ScenarioRunner:
    def __init__(self, agent=None):
        self.agent = agent

    def run_scenario(self, scenario: Dict[str, Any]) -> Dict[str, Any]:
        # Extremely lightweight: feed scenario events to agent if present
        events = scenario.get("events", [])
        for e in events:
            if self.agent and hasattr(self.agent, "ingest_report"):
                try:
                    self.agent.ingest_report(e)
                except Exception:
                    pass
            time.sleep(0.01)
        return {"status": "completed", "events": len(events)}


def sample_flood_scenario() -> Dict[str, Any]:
    return {
        "name": "flood",
        "events": [
            {"type": "hazard", "location": "river-1", "severity": 0.8},
            {"type": "hazard", "location": "bridge-2", "severity": 0.9},
        ],
    }
