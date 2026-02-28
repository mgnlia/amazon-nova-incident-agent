"""Tests for the FastAPI endpoints."""

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "healthy"
    assert data["version"] == "0.2.0"


def test_create_incident_mock():
    r = client.post("/incidents", json={
        "description": "High CPU on production EC2 instance i-0abc, response times degraded",
        "severity": "high",
        "service": "ec2",
        "use_mock": True,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "completed"
    assert len(data["diagnosis"]) > 50
    assert data["session_id"] is not None


def test_create_incident_validation():
    r = client.post("/incidents", json={"description": "short"})
    assert r.status_code == 422  # Pydantic validation error


def test_list_incidents():
    r = client.get("/incidents")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_get_incident_not_found():
    r = client.get("/incidents/nonexistent-id")
    assert r.status_code == 404


def test_demo_endpoint():
    r = client.post("/demo")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "completed"
    assert "5xx" in data["diagnosis"].lower() or "error" in data["diagnosis"].lower()


def test_incident_roundtrip():
    # Create
    r = client.post("/incidents", json={
        "description": "Lambda function timeout in production, 29s duration, throttling",
        "severity": "critical",
        "use_mock": True,
    })
    assert r.status_code == 200
    sid = r.json()["session_id"]

    # Retrieve
    r2 = client.get(f"/incidents/{sid}")
    assert r2.status_code == 200
    assert r2.json()["session_id"] == sid
