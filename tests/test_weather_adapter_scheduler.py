import unittest
import tempfile
import os
import time

from aegis_conduit.adapters.weather_adapter import WeatherAdapter
from aegis_conduit.adapters.scheduler import FeedScheduler
from aegis_conduit.routing import RouteEvaluator


class TestWeatherAdapterScheduler(unittest.TestCase):
    def test_file_polling_and_scheduler_calls_handler(self):
        adapter = WeatherAdapter()
        re = RouteEvaluator()
        re.load_topology()

        # temp ndjson file with two events
        tf = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".ndjson")
        try:
            tf.write('{"type":"weather","affected_edges":[{"from":"warehouse","to":"supply_depot","severity":0.4}]}\n')
            tf.flush()
            tf.close()

            called = []

            def poll_fn():
                return adapter.poll_file(tf.name)

            def handler(evt):
                called.append(evt)
                re.ingest_hazard({"event": evt})

            sched = FeedScheduler(poll_fn=poll_fn, handler=handler, interval=0.2)
            sched.start()
            time.sleep(0.4)
            sched.stop()

            self.assertTrue(len(called) >= 1)
            # confirm route risk changed for affected edge
            re.recalculate_routes([])
            after = {r['route_id']: r['risk_score'] for r in re.current_routes}
            affected = next((rid for rid in after if 'supply_depot' in rid), None)
            self.assertIsNotNone(affected)
            # Risk should be > 0 (default) and reflective of hazard
            self.assertGreater(after[affected], 0)

        finally:
            try:
                os.unlink(tf.name)
            except Exception:
                pass


if __name__ == '__main__':
    unittest.main()
