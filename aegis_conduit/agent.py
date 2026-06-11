"""Core crisis reasoning agent for decentralized logistics."""

from dataclasses import dataclass
from typing import Any

from .data_veracity import VeracityEngine
from .mesh_sync import MeshSyncEngine
from .routing import RouteEvaluator
from .utils import normalize_report
from .broadcast import RouteBroadcaster
from .anomaly import AnomalyDetector
from .agents.commander import CommanderAgent
import os
import pickle


@dataclass
class CrisisAgent:
    sync_engine: MeshSyncEngine
    veracity_engine: VeracityEngine
    route_evaluator: RouteEvaluator
    state: dict[str, Any] = None
    broadcaster: RouteBroadcaster | None = None

    def __post_init__(self):
        self.state = {
            "reports": [],
            "trusted_events": [],
            "routes": [],
        }
        # lightweight local anomaly detector for pre-filtering incoming reports
        try:
            self.anomaly_detector = AnomalyDetector()
        except Exception:
            self.anomaly_detector = None
        # attempt to load persisted sklearn model if present
        try:
            model_path = os.path.join(os.getcwd(), ".cache", "anomaly_model.pkl")
            if os.path.exists(model_path) and getattr(self, "anomaly_detector", None) is not None:
                with open(model_path, "rb") as mf:
                    loaded = pickle.load(mf)
                # attach loaded estimator if valid
                if loaded is not None:
                    try:
                        self.anomaly_detector.model = loaded
                    except Exception:
                        pass
        except Exception:
            # ignore loading errors
            pass
        # attach a commander agent for multi-agent coordination
        try:
            self.commander = CommanderAgent()
        except Exception:
            self.commander = None

    def bootstrap(self) -> None:
        """Initialize local agent state and connect mesh components."""
        self.sync_engine.start()
        self.route_evaluator.load_topology()

        # If mesh sync loaded a persisted state, adopt it as initial agent state
        persisted = getattr(self.sync_engine, "local_store", None)
        if persisted and persisted.get("reports"):
            # adopt persisted snapshot
            self.state = persisted.copy()
            # recompute routes from persisted trusted events
            try:
                self.route_evaluator.recalculate_routes(self.state.get("trusted_events", []))
                self.state["routes"] = self.route_evaluator.current_routes
            except Exception:
                pass

    def ingest_report(self, report: dict[str, Any]) -> None:
        """Process a new report from a mesh peer or local source."""
        normalized = normalize_report(report)
        # anomaly pre-check: drop extremely anomalous packets before expensive validation
        try:
            if getattr(self, "anomaly_detector", None) is not None:
                score = self.anomaly_detector.score_packet(normalized)
                if score >= 0.8:
                    # record anomaly and skip further processing
                    anomaly_record = {"trusted": False, "confidence": 0.0, "anomaly_score": score, "event": normalized.get("event"), "source": normalized.get("source")}
                    self.state["reports"].append(anomaly_record)
                    return
        except Exception:
            # if anomaly detection fails, continue with normal pipeline
            pass
        validated = self.veracity_engine.validate_report(normalized)
        if not validated["trusted"]:
            self.state["reports"].append(validated)
            return

        self.state["reports"].append(validated)
        self.state["trusted_events"].append(validated["event"])
        self.route_evaluator.update_risk(validated)
        # notify commander for mission planning; if a plan is returned, record and publish
        try:
            if getattr(self, "commander", None) is not None:
                plan = self.commander.handle_report(validated)
                if plan is not None:
                    self.state.setdefault("plans", []).append(plan)
                    if self.broadcaster:
                        try:
                            import asyncio

                            asyncio.get_event_loop().create_task(self.broadcaster.publish({"plan": plan}))
                        except Exception:
                            pass
        except Exception:
            pass

    def run_cycle(self) -> None:
        """Evaluate all trusted reports and refresh route recommendations."""
        self.sync_engine.sync_state(self.state)
        self.route_evaluator.recalculate_routes(self.state["trusted_events"])
        new_routes = self.route_evaluator.current_routes
        self.state["routes"] = new_routes

        # publish updates to subscribers if broadcaster present
        if self.broadcaster:
            # schedule publish asynchronously
            try:
                import asyncio

                asyncio.get_event_loop().create_task(self.broadcaster.publish({"routes": new_routes}))
            except Exception:
                # if event loop not running, ignore
                pass

    def produce_recommendations(self) -> list[dict[str, Any]]:
        """Return the current route recommendations."""
        return self.state["routes"]

    def run_loop(self) -> None:
        """Run the agent loop until stopped."""
        while True:
            incoming = self.sync_engine.receive()
            if incoming is not None:
                self.ingest_report(incoming)
            self.run_cycle()
