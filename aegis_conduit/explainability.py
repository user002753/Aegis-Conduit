"""Explainability helpers to produce operator-facing route rationales."""
from __future__ import annotations

from typing import Dict, Any, List


def explain_route(route: Dict[str, Any], context: Dict[str, Any]) -> str:
    reasons: List[str] = []
    if route.get("risk_reduction"):
        reasons.append(f"{route['risk_reduction']*100:.0f}% lower risk")
    if route.get("verified_bridges"):
        reasons.append(f"{route['verified_bridges']} bridge(s) verified operational")
    if context.get("confirmed_by"):
        reasons.append(f"confirmed by {len(context['confirmed_by'])} trusted sources")

    if not reasons:
        return "No strong reasons available; route selected by default scoring."
    return "Reasons:\n- " + "\n- ".join(reasons)
