import unittest

from aegis_conduit.mesh_sync import MeshSyncEngine


class TestMeshSync(unittest.TestCase):
    def test_peer_registration_and_gossip(self):
        a = MeshSyncEngine()
        b = MeshSyncEngine()
        self.addCleanup(a.close)
        self.addCleanup(b.close)

        a.register_peer(b)
        b.register_peer(a)

        report = {
            "source": "verified_ngo",
            "timestamp": "2026-06-09T13:00:00Z",
            "event": {"type": "road_block", "from": "x", "to": "y", "reference_id": "road_status_feed"},
        }

        a.post_local_report(report)
        # a has the report locally before gossip
        self.assertTrue(any(r for r in a.local_store["reports"] if r["source"] == "verified_ngo"))

        # gossip should propagate to b
        a.gossip()
        self.assertTrue(any(r for r in b.local_store["reports"] if r["source"] == "verified_ngo"))

    def test_duplicate_reports_are_not_replayed(self):
        engine = MeshSyncEngine()
        self.addCleanup(engine.close)

        report = {
            "source": "verified_ngo",
            "timestamp": "2026-06-09T13:00:00Z",
            "event": {"type": "road_block", "reference_id": "road_status_feed"},
        }

        engine.post_local_report(report)
        engine.post_local_report(dict(report))

        self.assertEqual(len(engine.local_store["reports"]), 1)
        self.assertIn(engine._report_key(report), engine.local_store["crdt"]["gset"])

    def test_authoritative_state_merges_routes_by_route_id(self):
        engine = MeshSyncEngine()
        self.addCleanup(engine.close)

        engine.sync_state(
            {
                "routes": [
                    {"route_id": "alpha", "risk_score": 0.2},
                    {"route_id": "alpha", "risk_score": 0.2},
                    {"route_id": "bravo", "risk_score": 0.4},
                ]
            }
        )

        self.assertEqual([route["route_id"] for route in engine.local_store["routes"]], ["alpha", "bravo"])


if __name__ == "__main__":
    unittest.main()
