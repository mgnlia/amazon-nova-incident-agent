"""Tests for tool definitions and mock executors."""

from agent.tools import TOOL_SPECS, execute_tool


def test_tool_specs_count():
    assert len(TOOL_SPECS) == 7


def test_all_tools_have_valid_schema():
    for spec in TOOL_SPECS:
        ts = spec["toolSpec"]
        assert "name" in ts
        assert "description" in ts
        assert "inputSchema" in ts
        assert "json" in ts["inputSchema"]
        schema = ts["inputSchema"]["json"]
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema


def test_cloudwatch_query():
    result = execute_tool("cloudwatch_query", {
        "namespace": "AWS/EC2",
        "metric_name": "CPUUtilization",
        "period_minutes": 60,
    })
    assert "datapoints" in result
    assert len(result["datapoints"]) > 0
    assert result["status"] == "ok"


def test_log_search():
    result = execute_tool("log_search", {
        "log_group": "/aws/lambda/my-func",
        "filter_pattern": "ERROR",
    })
    assert "events" in result
    assert result["events_found"] >= 0


def test_run_ssm_command():
    result = execute_tool("run_ssm_command", {
        "instance_id": "i-abc123",
        "command": "top -bn1",
    })
    assert result["status"] == "Success"
    assert "stdout" in result
    assert "%Cpu" in result["stdout"]


def test_describe_network():
    result = execute_tool("describe_network", {"resource_id": "i-abc123"})
    assert "vpc_id" in result
    assert "security_groups" in result


def test_get_iam_policy():
    result = execute_tool("get_iam_policy", {"principal": "TestRole"})
    assert "attached_policies" in result
    assert "inline_policies" in result


def test_run_sql_query():
    result = execute_tool("run_sql_query", {
        "cluster_arn": "arn:aws:rds:us-east-1:123:cluster:db",
        "database": "mydb",
        "sql": "SELECT state, count(*) FROM pg_stat_activity GROUP BY state",
    })
    assert "rows" in result
    assert result["rows_returned"] > 0


def test_retrieve_runbook_tool():
    result = execute_tool("retrieve_runbook", {
        "query": "high CPU on EC2",
        "top_k": 2,
    })
    assert "runbooks" in result
    assert result["runbooks_found"] > 0


def test_unknown_tool():
    result = execute_tool("nonexistent_tool", {})
    assert "error" in result
