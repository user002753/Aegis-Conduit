"""Commander Agent: orchestrates specialized agents to produce mission plans."""
from __future__ import annotations

from typing import Dict, Any, List, Optional
from .intel_agent import IntelAgent
from .routing_agent import RoutingAgent
from .supply_agent import SupplyAgent
from .mission_director import MissionDirector

from ..trust import TrustEngine
from ..mission_planner import MissionPlanner
from ..forecasting import ForecastingEngine
from ..resource_optimizer import ResourceOptimizer
from ..explainability import explain_route
from ..knowledge_graph import KnowledgeGraph
from .drone_agent import DroneAgent
from ..identity import IdentityManager


class CommanderAgent:
    def __init__(self):
        self.intel = IntelAgent()
        self.routing = RoutingAgent()
        self.supply = SupplyAgent()
        self.director = MissionDirector(self.intel, self.routing, self.supply)

        self.trust = TrustEngine()
        self.planner = MissionPlanner()
        self.forecaster = ForecastingEngine()
        self.optimizer = ResourceOptimizer()
        self.kg = KnowledgeGraph()
        self.drone = DroneAgent()
        self.identity = IdentityManager()

    def handle_report(self, report: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        # verify identity/signature if present
        try:
            if report.get("signature"):
                valid = self.identity.verify_report(report)
                report["_sig_ok"] = bool(valid)
        except Exception:
            report["_sig_ok"] = False

        # trust scoring. Validated reports from the VeracityEngine already
        # carry the fused trust/signature/registry confidence used by the API.
        trust = float(report.get("confidence", self.trust.trust_score(report)))
        report["_trust"] = trust

        # ingest into intel
        self.intel.ingest(report)

        # add to knowledge graph
        self.kg.add_report(report)

        # If hazard and trust high, trigger mission planning
        if report.get("type") == "hazard" and report.get("trusted", trust > 0.6):
            context = {
                "hazard": report,
                "population": 12450,
                "vehicles": [
                    {"id": "med-1", "type": "ambulance", "capacity": 4},
                    {"id": "truck-2", "type": "supply_truck", "capacity": 80},
                    {"id": "truck-3", "type": "supply_truck", "capacity": 80},
                ],
            }
            plan = self.planner.generate_plan(context, self.intel, self.supply, self.optimizer)
            return plan
        return None

    def request_drone_recon(self, target: Dict[str, Any]) -> Dict[str, Any]:
        return self.drone.recon(target)
