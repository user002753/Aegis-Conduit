"""Intel Agent: processes incoming reports and builds local situational awareness."""
from __future__ import annotations

from typing import Dict, Any, List


class IntelAgent:
    def __init__(self):
        self.reports: List[Dict[str, Any]] = []

    def ingest(self, report: Dict[str, Any]) -> None:
        self.reports.append(report)

    def summarize(self) -> Dict[str, Any]:
        return {"count": len(self.reports)}
