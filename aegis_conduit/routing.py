"""Route evaluation engine for dynamic crisis logistics."""

from datetime import datetime
from typing import Any

import networkx as nx


class RouteEvaluator:
    def __init__(self) -> None:
        self.current_routes: list[dict[str, Any]] = []
        self.topology = nx.DiGraph()
        # hazard multipliers keyed by (src, dst) -> additive risk
        self.hazards: dict[tuple[str, str], float] = {}

    def load_topology(self) -> None:
        """Load or initialize route graph and infrastructure data."""
        self.topology = nx.DiGraph()
        self.topology.add_edge("warehouse", "checkpoint", risk=0.2, distance=3)
        self.topology.add_edge("checkpoint", "evac_zone", risk=0.2, distance=2)
        self.topology.add_edge("warehouse", "medical_hub", risk=0.15, distance=4)
        self.topology.add_edge("medical_hub", "evac_zone", risk=0.3, distance=3)
        self.topology.add_edge("warehouse", "supply_depot", risk=0.1, distance=2)
        self.topology.add_edge("supply_depot", "evac_zone", risk=0.25, distance=4)

    def update_risk(self, validated_report: dict[str, Any]) -> None:
        """Adjust risk metrics in the route model based on trusted incident reports.

        Supports `road_block` events as before and also `weather` and `sensor`
        events which can include `affected_edges` with `from`, `to`, and
        `severity` attributes.
        """
        event = validated_report.get("event", {})
        etype = event.get("type")

        if etype == "road_block":
            origin = event.get("from")
            destination = event.get("to")
            if not origin or not destination:
                return
            if self.topology.has_edge(origin, destination):
                current_risk = self.topology.edges[origin, destination].get("risk", 0.2)
                added_risk = event.get("severity", 0.2)
                self.topology.edges[origin, destination]["risk"] = min(1.0, current_risk + added_risk)
            else:
                self.topology.add_edge(origin, destination, risk=0.8, distance=5)

        elif etype in ("weather", "sensor_alert"):
            # expect an array of affected edges in event["affected_edges"]
            for info in event.get("affected_edges", []):
                origin = info.get("from")
                destination = info.get("to")
                severity = float(info.get("severity", 0.2))
                if not origin or not destination:
                    continue
                # record hazard multiplier (additive)
                key = (origin, destination)
                self.hazards[key] = min(1.0, self.hazards.get(key, 0.0) + severity)

    def recalculate_routes(self, trusted_events: list[dict[str, Any]]) -> None:
        """Generate route recommendations and score alternatives."""
        self.current_routes = []
        source = "warehouse"
        target = "evac_zone"

        try:
            all_paths = list(nx.all_simple_paths(self.topology, source, target, cutoff=6))
        except nx.NetworkXNoPath:
            all_paths = []

        for path in all_paths:
            risk_score = self._route_risk(path)
            distance = self._route_distance(path)
            self.current_routes.append(
                {
                    "route_id": "-".join(path),
                    "path": path,
                    "risk_score": round(risk_score, 3),
                    "distance": distance,
                    "last_updated": datetime.utcnow().isoformat() + "Z",
                }
            )

        self.current_routes.sort(key=lambda route: (route["risk_score"], route["distance"]))
        self.current_routes = self.current_routes[:5]

    def _route_risk(self, path: list[str]) -> float:
        """Compute average risk along a path, factoring base edge risk and hazards."""
        per_edge = []
        for src, dst in zip(path, path[1:]):
            base = self.topology.edges[src, dst].get("risk", 0.5)
            hazard = self.hazards.get((src, dst), 0.0)
            # combined risk bounded by 1.0
            combined = min(1.0, base + hazard)
            per_edge.append(combined)
        if not per_edge:
            return 1.0
        return sum(per_edge) / len(per_edge)

    def _route_distance(self, path: list[str]) -> float:
        return sum(self.topology.edges[src, dst].get("distance", 1) for src, dst in zip(path, path[1:]))

    def ingest_hazard(self, hazard_event: dict[str, Any]) -> None:
        """Public method to ingest weather/sensor hazards directly.

        Accepts a dict with `type` and `affected_edges` similar to validated
        reports; this helper is useful for direct sensor streams.
        """
        evt = hazard_event.get("event") or hazard_event
        simulated = {"event": evt}
        self.update_risk({"event": evt})
