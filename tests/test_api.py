from fastapi.testclient import TestClient

from aegis_conduit.agent import CrisisAgent
from aegis_conduit.mesh_sync import MeshSyncEngine
from aegis_conduit.data_veracity import VeracityEngine
from aegis_conduit.routing import RouteEvaluator
from aegis_conduit.api import create_app


def setup_app():
    sync = MeshSyncEngine()
    veracity = VeracityEngine()
    routing = RouteEvaluator()
    agent = CrisisAgent(sync_engine=sync, veracity_engine=veracity, route_evaluator=routing)
    agent.bootstrap()
    app = create_app(agent)
    return app, agent


def test_post_report_and_get_routes():
    app, agent = setup_app()
    client = TestClient(app)

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

    resp = client.post("/report", json=report)
    assert resp.status_code == 200

    routes = client.get("/routes").json()
    assert isinstance(routes, list)
    assert len(routes) > 0


def test_post_hazard_changes_routes():
    app, agent = setup_app()
    client = TestClient(app)

    # baseline routes
    base = client.get("/routes").json()
    base_map = {r['route_id']: r['risk_score'] for r in base}

    hazard = {
        "event": {
            "type": "weather",
            "affected_edges": [{"from": "warehouse", "to": "supply_depot", "severity": 0.8}],
        }
    }

    resp = client.post("/hazard", json=hazard)
    assert resp.status_code == 200

    after = client.get("/routes").json()
    after_map = {r['route_id']: r['risk_score'] for r in after}

    affected = next((rid for rid in after_map if 'supply_depot' in rid), None)
    assert affected is not None
    assert after_map[affected] >= base_map.get(affected, 0)
