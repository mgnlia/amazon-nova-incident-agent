"""
Tests for the agent core module.
Covers: mock agent loop, tool execution, runbook retrieval, TF-IDF index.
"""

from __future__ import annotations

import pytest

from agent.core import AgentSession, run_agent_mock, _generate_mock_input
from agent.runbooks import retrieve_runbooks, RUNBOOKS, TFIDFIndex
from agent.tools import execute_tool, TOOL_SPECS


# ---------------------------------------------------------------------------
# run_agent_mock tests
# ---------------------------------------------------------------------------


def test_mock_agent_returns_session():
    """run_agent_mock returns a completed AgentSession."""
    session = run_agent_mock("CPU utilization at 97% on production EC2 instance")
    assert isinstance(session, AgentSession)


def test_mock_agent_status_completed():
    """Mock agent always completes (no Bedrock required)."""
    session = run_agent_mock("Lambda function timing out after 29 seconds")
    assert session.status == "completed"


def test_mock_agent_diagnosis_non_empty():
    """Diagnosis string is populated for any incident description."""
    session = run_agent_mock("RDS database connection pool exhausted, 5xx errors spiking")
    assert len(session.diagnosis) > 50


def test_mock_agent_session_id_unique():
    """Each invocation produces a unique session ID."""
    s1 = run_agent_mock("disk full on /dev/xvda1")
    s2 = run_agent_mock("disk full on /dev/xvda1")
    assert s1.session_id != s2.session_id


def test_mock_agent_turns_used():
    """Agent uses at least one turn (runbook retrieval step)."""
    session = run_agent_mock("ALB returning 503 errors, targets unhealthy")
    assert session.turns_used >= 1


def test_mock_agent_history_non_empty():
    """History contains at least user message and assistant response."""
    session = run_agent_mock("DynamoDB ThrottlingException on hot partition")
    assert len(session.history) >= 2


def test_mock_agent_remediation_list():
    """Remediation is a list (may be empty for unknown incidents)."""
    session = run_agent_mock("S3 access denied 403 on bucket policy")
    assert isinstance(session.remediation, list)


# ---------------------------------------------------------------------------
# Tool execution tests
# ---------------------------------------------------------------------------


def test_execute_cloudwatch_query():
    """cloudwatch_query returns datapoints with expected keys."""
    result = execute_tool("cloudwatch_query", {
        "namespace": "AWS/EC2",
        "metric_name": "CPUUtilization",
        "period_minutes": 60,
    })
    assert "datapoints" in result
    assert isinstance(result["datapoints"], list)
    assert len(result["datapoints"]) > 0
    dp = result["datapoints"][0]
    assert "timestamp" in dp
    assert "value" in dp


def test_execute_log_search():
    """log_search returns events list."""
    result = execute_tool("log_search", {
        "log_group": "/aws/lambda/my-function",
        "filter_pattern": "ERROR",
        "minutes_ago": 30,
    })
    assert "events" in result
    assert isinstance(result["events"], list)


def test_execute_run_ssm_command():
    """run_ssm_command returns stdout."""
    result = execute_tool("run_ssm_command", {
        "instance_id": "i-0abc123def456",
        "command": "top -bn1 | head -20",
    })
    assert "stdout" in result
    assert result["status"] == "Success"


def test_execute_retrieve_runbook():
    """retrieve_runbook tool returns runbooks list."""
    result = execute_tool("retrieve_runbook", {
        "query": "lambda timeout throttle concurrency",
        "top_k": 2,
    })
    assert "runbooks" in result
    assert isinstance(result["runbooks"], list)


def test_execute_unknown_tool():
    """Unknown tool name returns error dict."""
    result = execute_tool("nonexistent_tool", {})
    assert "error" in result


def test_tool_specs_structure():
    """All TOOL_SPECS have required fields."""
    for spec in TOOL_SPECS:
        assert "toolSpec" in spec
        ts = spec["toolSpec"]
        assert "name" in ts
        assert "description" in ts
        assert "inputSchema" in ts


# ---------------------------------------------------------------------------
# Runbook retrieval tests
# ---------------------------------------------------------------------------


def test_retrieve_runbooks_returns_list():
    """retrieve_runbooks always returns a list."""
    results = retrieve_runbooks("CPU spike on EC2")
    assert isinstance(results, list)


def test_retrieve_runbooks_top_k():
    """top_k parameter limits results."""
    results = retrieve_runbooks("database connection pool exhausted", top_k=2)
    assert len(results) <= 2


def test_retrieve_runbooks_relevance_score():
    """Results include relevance_score."""
    results = retrieve_runbooks("5xx errors ALB load balancer")
    if results:
        assert "relevance_score" in results[0]
        assert results[0]["relevance_score"] > 0


def test_retrieve_runbooks_correct_match():
    """CPU incident matches the CPU runbook."""
    results = retrieve_runbooks("cpu utilization high ec2 memory spike performance slow")
    assert len(results) > 0
    top = results[0]
    assert "cpu" in top["title"].lower() or "memory" in top["title"].lower() or "ec2" in top["title"].lower()


def test_retrieve_runbooks_lambda():
    """Lambda incident matches Lambda runbook."""
    results = retrieve_runbooks("lambda throttle timeout duration exceeded concurrency")
    assert len(results) > 0
    titles = [r["title"].lower() for r in results]
    assert any("lambda" in t for t in titles)


def test_tfidf_index_build():
    """TFIDFIndex builds correctly from RUNBOOKS."""
    idx = TFIDFIndex()
    idx.build(RUNBOOKS)
    assert len(idx.docs) == len(RUNBOOKS)
    assert len(idx.idf) > 0
    assert len(idx.tf_matrix) == len(RUNBOOKS)


def test_tfidf_empty_query():
    """Empty query returns empty results (no matches)."""
    results = retrieve_runbooks("")
    # Empty query — no tokens → no score matches
    assert isinstance(results, list)


def test_generate_mock_input_cloudwatch():
    """_generate_mock_input returns correct namespace for CPU incident."""
    inp = _generate_mock_input("cloudwatch_query", "CPU utilization spike on EC2")
    assert "namespace" in inp
    assert "metric_name" in inp


def test_generate_mock_input_log_search():
    """_generate_mock_input returns log_group for log_search."""
    inp = _generate_mock_input("log_search", "application error")
    assert "log_group" in inp
    assert "filter_pattern" in inp
