import unittest

from aegis_conduit.routing import RouteEvaluator


class TestRoutingHazards(unittest.TestCase):
    def setUp(self):
        self.re = RouteEvaluator()
        self.re.load_topology()

    def test_weather_hazard_increases_edge_risk(self):
        # baseline routes
        self.re.recalculate_routes([])
        base = {r['route_id']: r['risk_score'] for r in self.re.current_routes}
        # Inject a weather hazard affecting warehouse->supply_depot
        hazard = {
            'type': 'weather',
            'affected_edges': [
                {'from': 'warehouse', 'to': 'supply_depot', 'severity': 0.6}
            ]
        }
        self.re.ingest_hazard({'event': hazard})
        self.re.recalculate_routes([])
        after = {r['route_id']: r['risk_score'] for r in self.re.current_routes}

        # Find a route containing that edge
        affected_route_id = None
        for rid in after:
            if 'supply_depot' in rid:
                affected_route_id = rid
                break

        self.assertIsNotNone(affected_route_id)
        self.assertGreater(after[affected_route_id], base.get(affected_route_id, 0.0))


if __name__ == '__main__':
    unittest.main()
