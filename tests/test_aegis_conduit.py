import unittest
import json

from aegis_conduit.agent import CrisisAgent
from aegis_conduit import resource_optimizer as resource_optimizer_module
from aegis_conduit.data_veracity import VeracityEngine
from aegis_conduit.identity import IdentityManager
from aegis_conduit.mesh_sync import MeshSyncEngine
from aegis_conduit.resource_optimizer import ResourceOptimizer
from aegis_conduit.routing import RouteEvaluator


class TestAegisConduit(unittest.TestCase):
    def setUp(self):
        self.sync = MeshSyncEngine()
        self.veracity = VeracityEngine()
        self.routing = RouteEvaluator()
        self.agent = CrisisAgent(
            sync_engine=self.sync,
            veracity_engine=self.veracity,
            route_evaluator=self.routing,
        )
        self.agent.bootstrap()

    def test_trusted_report_is_processed(self):
        report = {
            "source": "red_cross",
            "type": "infrastructure_update",
            "timestamp": "2026-06-09T12:00:00Z",
            "event": {
                "type": "road_block",
                "from": "warehouse",
                "to": "checkpoint",
                "severity": 0.5,
                "status": "blocked",
                "reference_id": "road_status_feed",
                "verified_by": "red_cross",
            },
        }

        self.agent.sync_engine.post_local_report(report)
        incoming = self.agent.sync_engine.receive()
        self.agent.ingest_report(incoming)
        self.agent.run_cycle()

        self.assertTrue(self.agent.state["reports"])
        self.assertTrue(self.agent.state["routes"])
        self.assertEqual(self.agent.state["reports"][0]["source"], "red_cross")

    def test_route_evaluator_generates_routes(self):
        self.routing.recalculate_routes([])
        self.assertGreaterEqual(len(self.routing.current_routes), 1)
        route = self.routing.current_routes[0]
        self.assertIn("path", route)
        self.assertIn("risk_score", route)

    def test_signed_authority_report_is_trusted_and_tamper_fails(self):
        identity = IdentityManager()
        event = {
            "type": "road_block",
            "from": "warehouse",
            "to": "checkpoint",
            "severity": 0.7,
            "status": "authenticated",
            "reference_id": "road_status_feed",
            "verified_by": "district_authority",
        }
        body = json.dumps(event, sort_keys=True).encode("utf-8")
        report = {
            "source": "district_authority",
            "type": "hazard",
            "timestamp": "2026-06-09T12:00:00Z",
            "event": event,
            "body": body.decode("utf-8"),
            "signature": identity.sign(body).hex(),
            "public_key": identity.public_key_hex(),
        }

        result = self.veracity.validate_report(report)
        self.assertTrue(result["trusted"])
        self.assertTrue(result["crypto_valid"])

        tampered = dict(report)
        tampered["body"] = '{"type":"road_clear"}'
        tampered_result = self.veracity.validate_report(tampered)
        self.assertFalse(tampered_result["crypto_valid"])

    def test_resource_optimizer_fallback_respects_capacity(self):
        previous = resource_optimizer_module._HAS_ORTOOLS
        resource_optimizer_module._HAS_ORTOOLS = False
        self.addCleanup(setattr, resource_optimizer_module, "_HAS_ORTOOLS", previous)
        optimizer = ResourceOptimizer()
        assignments = optimizer.assign(
            [{"id": "small", "capacity": 5}, {"id": "large", "capacity": 20}],
            [{"id": "medical", "demand": 12}, {"id": "water", "demand": 4}],
        )

        self.assertEqual(assignments, [("large", "medical"), ("small", "water")])


if __name__ == "__main__":
    unittest.main()
