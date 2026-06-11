"""Mission planner: generate multi-phase mission plans from context and resources."""
from __future__ import annotations

from typing import Dict, Any, List
import math


class MissionPlanner:
    def __init__(self):
        pass

    def generate_plan(self, context: Dict[str, Any], intel_agent, supply_agent, optimizer) -> Dict[str, Any]:
        """Produce a simple mission plan with phases.

        This is a heuristic planner for demo purposes: it creates evacuation and
        supply phases and estimates time/casualty reduction heuristics.
        """
        hazard = context.get("hazard", {})
        population = context.get("population", 100)
        shelters = context.get("shelters", 3)
        vehicles = context.get("vehicles", [])

        # Phase 1: Immediate evacuations (assign up to vehicles available)
        evac_count = min(population, len(vehicles) * 20)
        phase1 = {
            "name": "Evacuate high-risk sectors",
            "action": f"Evacuate up to {evac_count} people using {len(vehicles)} vehicles",
            "estimated_time_hr": max(1, math.ceil(evac_count / 50)),
        }

        # Phase 2: Deploy medical
        med_veh = [v for v in vehicles if v.get("type") == "ambulance"]
        phase2 = {
            "name": "Deploy medical response",
            "action": f"Dispatch {len(med_veh)} ambulances",
            "estimated_time_hr": 1,
        }

        # Phase 3: Resupply
        assignments = optimizer.assign(vehicles, [{"id": "supply1"}])
        phase3 = {"name": "Resupply", "action": f"Assignments: {assignments}", "estimated_time_hr": 2}

        # Simple impact estimate
        est_casualties_reduced = int(min(50, evac_count * 0.15))

        plan = {
            "hazard": hazard,
            "phases": [phase1, phase2, phase3],
            "estimated_casualties_reduced": est_casualties_reduced,
            "confidence": 0.7,
        }
        return plan
