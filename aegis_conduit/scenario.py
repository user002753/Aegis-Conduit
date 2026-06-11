"""Scenario runner for local Aegis Conduit demonstration."""


from .agent import CrisisAgent
from .adapters.weather_feed import WeatherFeedSimulator
from .adapters.weather_adapter import WeatherAdapter
from .adapters.scheduler import FeedScheduler


class ScenarioRunner:
    def __init__(self, agent: CrisisAgent) -> None:
        self.agent = agent

    def run(self) -> None:
        self.agent.bootstrap()

        reports = [
            {
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
            },
            {
                "source": "verified_ngo",
                "type": "logistics_update",
                "timestamp": "2026-06-09T12:01:00Z",
                "event": {
                    "type": "road_block",
                    "from": "medical_hub",
                    "to": "evac_zone",
                    "severity": 0.4,
                    "status": "blocked",
                    "reference_id": "road_status_feed",
                    "verified_by": "verified_ngo",
                },
            },
            {
                "source": "local_command_center",
                "type": "status_report",
                "timestamp": "2026-06-09T12:02:00Z",
                "event": {
                    "type": "road_clear",
                    "from": "supply_depot",
                    "to": "evac_zone",
                    "severity": 0.0,
                    "status": "clear",
                    "reference_id": "road_status_feed",
                    "verified_by": "local_command_center",
                },
            },
        ]

        for idx, report in enumerate(reports, start=1):
            self.agent.sync_engine.post_local_report(report)
            incoming = self.agent.sync_engine.receive()
            if incoming is not None:
                self.agent.ingest_report(incoming)
            self.agent.run_cycle()
            print(f"=== Cycle {idx} ===")
            for route in self.agent.produce_recommendations():
                print(f"Route {route['route_id']}: path={route['path']} risk={route['risk_score']} distance={route['distance']}")
            print()

        # Demonstrate continuous weather feed integration
        # File-based adapter demonstration
        feed = WeatherFeedSimulator()
        # A simulated rainstorm increases severity on warehouse->supply_depot
        feed.add_event({
            "type": "weather",
            "affected_edges": [{"from": "warehouse", "to": "supply_depot", "severity": 0.5}],
        })

        for evt in feed.stream():
            # route_evaluator can ingest hazard events directly
            self.agent.route_evaluator.ingest_hazard({"event": evt})
            self.agent.run_cycle()
            print("=== After weather event ===")
            for route in self.agent.produce_recommendations():
                print(f"Route {route['route_id']}: path={route['path']} risk={route['risk_score']} distance={route['distance']}")
            print()

        # Demonstrate file-based continuous polling via WeatherAdapter + scheduler
        adapter = WeatherAdapter()
        # create a small temp file with one event for the example (consumer may supply real path)
        import tempfile, os

        tf = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".ndjson")
        try:
            tf.write('{"type":"weather","affected_edges":[{"from":"warehouse","to":"checkpoint","severity":0.3}]}\n')
            tf.flush()
            tf.close()

            def poll_fn():
                return adapter.poll_file(tf.name)

            def handler(evt):
                self.agent.route_evaluator.ingest_hazard({"event": evt})

            sched = FeedScheduler(poll_fn=poll_fn, handler=handler, interval=1.0)
            sched.start()
            # run one polling cycle for demo
            import time
            time.sleep(1.2)
            sched.stop()
        finally:
            try:
                os.unlink(tf.name)
            except Exception:
                pass
