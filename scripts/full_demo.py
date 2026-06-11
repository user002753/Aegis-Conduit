#!/usr/bin/env python3
"""Deterministic judge demo for Aegis Conduit.

Runs the full local proof path in-process:

1. Reject an unsigned spoofed report.
2. Accept an authority-signed report with signature verification.
3. Re-rank evacuation routes from the trusted hazard.
4. Generate a mission plan and resource assignments.
5. Merge offline mesh replicas through CRDT-backed gossip.
"""
from __future__ import annotations

import json
import sys
from time import perf_counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aegis_conduit.agent import CrisisAgent
from aegis_conduit.data_veracity import VeracityEngine
from aegis_conduit.identity import IdentityManager
from aegis_conduit.mesh_sync import MeshSyncEngine
from aegis_conduit.resource_optimizer import ResourceOptimizer
from aegis_conduit.routing import RouteEvaluator


def _print_step(title: str, payload: object) -> None:
    print(f"\n=== {title} ===")
    print(json.dumps(payload, indent=2, sort_keys=True))


def _signed_report(identity: IdentityManager) -> dict:
    event = {
        "type": "road_block",
        "from": "warehouse",
        "to": "checkpoint",
        "severity": 0.72,
        "status": "authenticated",
        "reference_id": "road_status_feed",
        "verified_by": "district_authority",
    }
    body = json.dumps(event, sort_keys=True).encode("utf-8")
    signature = identity.sign(body)
    return {
        "source": "district_authority",
        "type": "hazard",
        "timestamp": "2026-06-09T12:00:00Z",
        "event": event,
        "body": body.decode("utf-8"),
        "signature": signature.hex(),
        "public_key": identity.public_key_hex(),
    }


def run_demo() -> dict:
    sync = MeshSyncEngine()
    peer = MeshSyncEngine()
    try:
        sync.register_peer(peer)
        peer.register_peer(sync)

        veracity = VeracityEngine()
        routing = RouteEvaluator()
        agent = CrisisAgent(sync_engine=sync, veracity_engine=veracity, route_evaluator=routing)
        agent.bootstrap()
        agent.run_cycle()
        baseline_routes = list(agent.produce_recommendations())

        spoofed = {
            "source": "anonymous_user_42",
            "type": "hazard",
            "timestamp": "2026-06-09T11:59:00Z",
            "event": {
                "type": "road_block",
                "from": "warehouse",
                "to": "checkpoint",
                "severity": 1.0,
                "status": "blocked",
                "reference_id": "unknown_social_claim",
            },
        }
        spoof_started = perf_counter()
        spoof_result = veracity.validate_report(spoofed)
        spoof_ms = (perf_counter() - spoof_started) * 1000
        _print_step("Spoofed report rejected", spoof_result)

        authority_identity = IdentityManager()
        report = _signed_report(authority_identity)
        signed_started = perf_counter()
        signature_valid = veracity.identity.verify_report(report)

        sync.post_local_report(report)
        incoming = sync.receive()
        if incoming is not None:
            agent.ingest_report(incoming)
        agent.run_cycle()
        signed_to_routes_ms = (perf_counter() - signed_started) * 1000

        accepted_report = agent.state["reports"][-1]
        ranked_routes = agent.produce_recommendations()
        mission_plan = agent.state.get("plans", [])[-1]

        optimizer = ResourceOptimizer()
        optimization_started = perf_counter()
        assignments = optimizer.assign(
            [
                {"id": "med-1", "type": "ambulance", "capacity": 10},
                {"id": "truck-2", "type": "supply_truck", "capacity": 80},
                {"id": "truck-3", "type": "supply_truck", "capacity": 80},
            ],
            [
                {"id": "insulin_cold_chain", "demand": 12},
                {"id": "water_sector_a", "demand": 60},
                {"id": "battery_packs", "demand": 20},
            ],
        )
        optimization_ms = (perf_counter() - optimization_started) * 1000

        mesh_started = perf_counter()
        peer.post_local_report(
            {
                "source": "verified_ngo",
                "timestamp": "2026-06-09T12:04:00Z",
                "event": {
                    "type": "road_clear",
                    "from": "supply_depot",
                    "to": "evac_zone",
                    "reference_id": "road_status_feed",
                },
            }
        )
        sync.gossip()
        mesh_merge_ms = (perf_counter() - mesh_started) * 1000

        proof = {
            "signature_valid": signature_valid,
            "accepted_report": {
                "trusted": accepted_report["trusted"],
                "confidence": round(accepted_report["confidence"], 3),
                "crypto_valid": accepted_report["crypto_valid"],
            },
            "baseline_best_route": baseline_routes[0]["route_id"],
            "post_hazard_best_route": ranked_routes[0]["route_id"],
            "post_hazard_routes": ranked_routes[:3],
            "mission_plan": {
                "phases": mission_plan["phases"],
                "estimated_casualties_reduced": mission_plan["estimated_casualties_reduced"],
                "confidence": mission_plan["confidence"],
            },
            "resource_assignments": assignments,
            "mesh_merge": {
                "node_a_reports": len(sync.local_store["reports"]),
                "node_b_reports": len(peer.local_store["reports"]),
                "crdt_keys": len(sync.local_store["crdt"]["gset"]),
            },
            "benchmark_ms": {
                "spoof_rejection": round(spoof_ms, 2),
                "signed_report_to_ranked_routes": round(signed_to_routes_ms, 2),
                "resource_assignment": round(optimization_ms, 2),
                "mesh_merge": round(mesh_merge_ms, 2),
            },
        }

        _print_step("Authority-signed report accepted", proof["accepted_report"])
        _print_step("Routes re-ranked", proof["post_hazard_routes"])
        _print_step("Mission plan generated", proof["mission_plan"])
        _print_step("Resource assignments", proof["resource_assignments"])
        _print_step("Offline mesh recovered", proof["mesh_merge"])
        _print_step("Demo benchmark", proof["benchmark_ms"])
        return proof
    finally:
        sync.close()
        peer.close()


if __name__ == "__main__":
    result = run_demo()
    if not result["signature_valid"] or not result["accepted_report"]["trusted"]:
        raise SystemExit(1)
