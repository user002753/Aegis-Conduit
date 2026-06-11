from typing import Any, Dict, List


class PolicyEngine:
    """Simple rule-based policy engine for route authorization.

    Rules are evaluated in order; the first rule that returns a blocking
    decision will mark the route as forbidden. Rules receive the `route`
    dict produced by `RouteEvaluator` and a `context` dict with mission params.
    """

    def __init__(self) -> None:
        self.rules = [self.security_hazard_rule, self.vehicle_weight_rule]

    def evaluate(self, route: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        reasons: List[str] = []
        allowed = True
        for rule in self.rules:
            ok, reason = rule(route, context)
            if not ok:
                allowed = False
                reasons.append(reason)
        return {"allowed": allowed, "reasons": reasons}

    def security_hazard_rule(self, route: Dict[str, Any], context: Dict[str, Any]):
        """Forbid civilian evacuation if any edge in the route has a very high hazard."""
        hazards = context.get("hazards_map", {})
        path = route.get("path", [])
        for src, dst in zip(path, path[1:]):
            h = hazards.get((src, dst), 0.0)
            if h >= 4.0:
                return False, f"Security hazard on {src}->{dst} with severity {h}"
        return True, ""

    def vehicle_weight_rule(self, route: Dict[str, Any], context: Dict[str, Any]):
        """Enforce bridge/weight limits encoded in a simple forbidden node list."""
        load = float(context.get("vehicle_load_tons", 0.0))
        if load <= 5.0:
            return True, ""
        # if heavy load and path uses sensitive node, forbid
        forbidden_nodes_for_heavy = context.get("heavy_forbidden_nodes", ["supply_depot"]) or []
        for node in route.get("path", []):
            if node in forbidden_nodes_for_heavy:
                return False, f"Vehicle load {load}t exceeds limit for node {node}"
        return True, ""
