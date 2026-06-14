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


def test_foundry_ground_endpoint():
    app, agent = setup_app()
    client = TestClient(app)
    
    payload = {
        "event": {
            "reference_id": "road_status_feed",
            "status": "authenticated"
        }
    }
    resp = client.post("/foundry/ground", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["trusted"] is True
    assert data["citations"][0]["source"] == "mock_foundry_iq"


def test_foundry_iq_cross_reference_with_mock_client():
    import os
    from unittest.mock import patch
    from aegis_conduit.foundry_iq import FoundryIQ

    app, agent = setup_app()
    client = TestClient(app)
    
    with patch.dict(os.environ, {
        "ENABLE_FOUNDRY": "true",
        "FOUNDRY_API_URL": "http://testserver/foundry",
        "FOUNDRY_API_KEY": "test-key"
    }):
        fi = FoundryIQ()
        assert fi.is_connected() is True
        
        event = {
            "reference_id": "road_status_feed",
            "status": "authenticated"
        }
        
        def mock_post(url, headers, data, timeout):
            assert url == "http://testserver/foundry/ground"
            assert headers["Authorization"] == "Bearer test-key"
            resp = client.post("/foundry/ground", content=data)
            class MockResponse:
                status_code = resp.status_code
                def json(self):
                    return resp.json()
            return MockResponse()
            
        with patch("requests.post", side_effect=mock_post):
            result = fi.cross_reference(event)
            assert result["trusted"] is True
            assert result["citations"][0]["source"] == "mock_foundry_iq"

