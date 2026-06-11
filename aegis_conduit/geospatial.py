"""Geospatial intelligence helpers: heatmaps and terrain-aware scoring."""
from __future__ import annotations

from typing import List, Dict, Any


def compute_heatmap(samples: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Return a simple aggregated heatmap (bbox & counts) for demo purposes."""
    counts = {}
    for s in samples:
        loc = s.get("location") or s.get("latlon") or "unknown"
        counts[loc] = counts.get(loc, 0) + 1
    return {"counts": counts}


def terrain_aware_risk(base_risk: float, terrain_factors: Dict[str, float]) -> float:
    """Adjust risk by terrain factors (elevation, watercrossing, road_type)."""
    modifier = 1.0
    for v in terrain_factors.values():
        modifier += float(v)
    return base_risk * modifier
