"""Tests for FastAPI endpoints."""

import pytest
from fastapi.testclient import TestClient
from sentinel.api.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_root_serves_dashboard(client):
    """Verify root / serves the React dashboard index.html."""
    res = client.get("/")
    assert res.status_code == 200
    assert "SENTINEL" in res.text


def test_health_endpoint(client):
    """Verify health status endpoint returns valid metadata."""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "HEALTHY"
    assert data["mode"] == "OFFLINE_DETERMINISTIC"
    assert data["rules_count"] >= 10


def test_rules_listing_and_toggle(client):
    """Verify rules listing and enable/disable toggle."""
    res = client.get("/api/rules")
    assert res.status_code == 200
    rules = res.json()
    assert len(rules) >= 10
    rule_id = rules[0]["id"]

    # Toggle rule
    toggle_res = client.post(f"/api/rules/{rule_id}/toggle")
    assert toggle_res.status_code == 200
    assert toggle_res.json()["rule_id"] == rule_id


def test_simulate_observation_fall_and_acknowledge(client):
    """Verify observation simulation endpoint and acknowledgment workflow."""
    payload = {
        "person_id": "api_test_person",
        "activity": "LYING_ON_FLOOR",
        "torso_angle": 88.0,
        "relative_body_height": 0.15,
        "vertical_velocity": 1.25,
        "vertical_acceleration": 0.0,
        "movement_velocity": 0.02,
        "motion_intensity": 0.02,
        "floor_proximity": 0.02,
        "zone_name": "FLOOR",
        "confidence": 0.95,
        "timestamp": 5000.0,
        "current_hour": 14,
    }
    res = client.post("/api/simulate-observation", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["person_id"] == "api_test_person"
    assert data["current_activity"] == "LYING_ON_FLOOR"
    assert len(data["incidents"]) >= 1

    inc_id = data["incidents"][0]["incident_id"]

    # Detail endpoint
    detail_res = client.get(f"/api/incidents/{inc_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["incident_id"] == inc_id
    assert detail["risk_level"] == "URGENT"

    # Acknowledge endpoint
    ack_res = client.post(
        f"/api/incidents/{inc_id}/acknowledge",
        json={"operator": "Nurse_Alex", "notes": "Responding immediately."},
    )
    assert ack_res.status_code == 200
    assert ack_res.json()["status"] == "ACKNOWLEDGED"

    # Resolve endpoint
    res_res = client.post(
        f"/api/incidents/{inc_id}/resolve",
        json={"operator": "Nurse_Alex", "notes": "Person assisted to chair."},
    )
    assert res_res.status_code == 200
    assert res_res.json()["status"] == "RESOLVED"
