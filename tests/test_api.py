"""
Tests for the FastAPI application.
Covers: POST /incidents, GET /incidents, GET /incidents/{id},
        GET /health, POST /demo, 404 handling.
"""

from __future__ import annotations

import os
import pytest

# Force mock mode so tests never need AWS credentials
os.environ.setdefault("MOCK_MODE", "true")

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------


def test_health_returns_200():
    """GET /health returns HTTP 200."""
    resp = client.get("/health")
    assert resp.status_code == 200


def test_health_response_shape():
    """GET /health returns status, version, model fields."""
    resp = client.get("/health")
    data = resp.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "model" in data


# ---------------------------------------------------------------------------
# POST /incidents
# ---------------------------------------------------------------------------


def test_create_incident_mock_mode():
    """POST /incidents with use_mock=true returns 200 and a session_id."""
    resp = client.post("/incidents", json={
        "description": "CPU utilization at 97% on production EC2 instance i-0abc123",
        "severity": "critical",
        "service": "payment-service",
        "use_mock": True,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert data["session_id"]


def test_create_incident_response_fields():
    """POST /incidents response contains all required fields."""
    resp = client.post("/incidents", json={
        "description": "Lambda function timing out after 29 seconds on checkout",
        "use_mock": True,
    })
    assert resp.status_code == 200
    data = resp.json()
    required = ["session_id", "status", "turns_used", "model_id", "diagnosis", "remediation", "created_at"]
    for field in required:
        assert field in data, f"Missing field: {field}"


def test_create_incident_status_completed():
    """Incident status is 'completed' after mock run."""
    resp = client.post("/incidents", json={
        "description": "RDS database connection pool exhausted, too many connections",
        "use_mock": True,
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


def test_create_incident_diagnosis_non_empty():
    """Diagnosis field is populated."""
    resp = client.post("/incidents", json={
        "description": "ALB returning 503 errors, 3 of 5 targets unhealthy after deployment",
        "use_mock": True,
    })
    assert resp.status_code == 200
    assert len(resp.json()["diagnosis"]) > 20


def test_create_incident_remediation_is_list():
    """Remediation field is always a list."""
    resp = client.post("/incidents", json={
        "description": "DynamoDB ThrottlingException on hot partition key",
        "use_mock": True,
    })
    assert resp.status_code == 200
    assert isinstance(resp.json()["remediation"], list)


def test_create_incident_description_too_short():
    """POST /incidents rejects description shorter than 10 chars."""
    resp = client.post("/incidents", json={
        "description": "short",
        "use_mock": True,
    })
    assert resp.status_code == 422


def test_create_incident_missing_description():
    """POST /incidents rejects missing description field."""
    resp = client.post("/incidents", json={"use_mock": True})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /incidents/{session_id}
# ---------------------------------------------------------------------------


def test_get_incident_by_id():
    """GET /incidents/{session_id} retrieves a previously created incident."""
    # Create one first
    create_resp = client.post("/incidents", json={
        "description": "ECS task crash looping with OOMKilled exit code",
        "use_mock": True,
    })
    assert create_resp.status_code == 200
    session_id = create_resp.json()["session_id"]

    get_resp = client.get(f"/incidents/{session_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["session_id"] == session_id


def test_get_incident_not_found():
    """GET /incidents/{session_id} returns 404 for unknown session."""
    resp = client.get("/incidents/nonexistent-session-id-xyz-999")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /incidents (list)
# ---------------------------------------------------------------------------


def test_list_incidents_returns_list():
    """GET /incidents returns a list."""
    resp = client.get("/incidents")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_list_incidents_includes_created():
    """GET /incidents includes newly created incidents."""
    create_resp = client.post("/incidents", json={
        "description": "VPC connectivity failure — instances cannot reach NAT gateway",
        "use_mock": True,
    })
    session_id = create_resp.json()["session_id"]

    list_resp = client.get("/incidents")
    ids = [i["session_id"] for i in list_resp.json()]
    assert session_id in ids


# ---------------------------------------------------------------------------
# POST /demo
# ---------------------------------------------------------------------------


def test_demo_endpoint():
    """POST /demo runs a canned demo incident and returns a valid response."""
    resp = client.post("/demo")
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert data["status"] == "completed"
    assert len(data["diagnosis"]) > 20
