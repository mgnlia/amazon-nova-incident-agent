"""Tests for the agent core — mock mode only (no AWS credentials needed)."""

from agent.core import run_agent_mock, AgentSession


def test_mock_agent_cpu_incident():
    session = run_agent_mock("High CPU utilization on production EC2 instance i-0abc123")
    assert session.status == "completed"
    assert session.turns_used > 0
    assert len(session.diagnosis) > 100
    assert len(session.history) > 0


def test_mock_agent_5xx_incident():
    session = run_agent_mock("5xx errors on ALB, 200 errors per minute, checkout failing")
    assert session.status == "completed"
    assert "5xx" in session.diagnosis.lower() or "error" in session.diagnosis.lower()


def test_mock_agent_database_incident():
    session = run_agent_mock("RDS PostgreSQL max connections exceeded, app returning 500s")
    assert session.status == "completed"
    assert len(session.remediation) > 0


def test_mock_agent_lambda_incident():
    session = run_agent_mock("Lambda function timing out after 29 seconds, throttling errors")
    assert session.status == "completed"


def test_mock_agent_session_fields():
    session = run_agent_mock("S3 access denied errors on bucket app-data")
    assert session.session_id is not None
    assert session.model_id == "mock"
    assert isinstance(session.remediation, list)
    assert isinstance(session.history, list)


def test_mock_agent_container_crash():
    session = run_agent_mock("ECS tasks in crash loop, OOMKilled, container restarting every 30s")
    assert session.status == "completed"
    assert session.turns_used >= 1


def test_agent_session_dataclass():
    s = AgentSession(session_id="test-123")
    assert s.model_id == "amazon.nova-pro-v1:0"
    assert s.status == "active"
    assert s.turns_used == 0
    assert s.history == []
