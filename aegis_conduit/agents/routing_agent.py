"""Routing Agent: specialized routing reasoning."""
from __future__ import annotations

from typing import Dict, Any, List


class RoutingAgent:
    def __init__(self):
        self.routes: List[Dict[str, Any]] = []

    def evaluate(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        # placeholder: return an empty route list
        return []
