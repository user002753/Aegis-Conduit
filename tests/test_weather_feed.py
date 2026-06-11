import unittest

from aegis_conduit.adapters.weather_feed import WeatherFeedSimulator
from aegis_conduit.routing import RouteEvaluator


class TestWeatherFeedIntegration(unittest.TestCase):
    def setUp(self):
        self.re = RouteEvaluator()
        self.re.load_topology()

    def test_feed_increases_hazard(self):
        self.re.recalculate_routes([])
        base = {r['route_id']: r['risk_score'] for r in self.re.current_routes}

        feed = WeatherFeedSimulator()
        feed.add_event({
            'type': 'weather',
            'affected_edges': [{'from': 'warehouse', 'to': 'supply_depot', 'severity': 0.7}],
        })

        for evt in feed.stream():
            self.re.ingest_hazard({'event': evt})

        self.re.recalculate_routes([])
        after = {r['route_id']: r['risk_score'] for r in self.re.current_routes}

        # Ensure risk increased for a path including supply_depot
        affected_route_id = next((rid for rid in after if 'supply_depot' in rid), None)
        self.assertIsNotNone(affected_route_id)
        self.assertGreater(after[affected_route_id], base.get(affected_route_id, 0.0))


if __name__ == '__main__':
    unittest.main()
