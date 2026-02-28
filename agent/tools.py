"""
Tool definitions for the agentic loop.
Each tool is defined as a Nova-compatible toolSpec and has a mock executor.
In production, executors call real AWS APIs via boto3.
"""

from __future__ import annotations
import json
import random
from datetime import datetime, timedelta, timezone

TOOL_SPECS: list[dict] = [
    {
        "toolSpec": {
            "name": "cloudwatch_query",
            "description": "Query CloudWatch metrics for a given namespace, metric, and time range. Returns datapoints.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "namespace": {
                            "type": "string",
                            "description": "CloudWatch namespace (e.g. AWS/EC2, AWS/RDS, AWS/Lambda)",
                        },
                        "metric_name": {
                            "type": "string",
                            "description": "Metric name (e.g. CPUUtilization, DatabaseConnections)",
                        },
                        "dimensions": {
                            "type": "object",
                            "description": "Key-value dimension filters",
                        },
                        "period_minutes": {
                            "type": "integer",
                            "description": "Lookback period in minutes (default 60)",
                        },
                    },
                    "required": ["namespace", "metric_name"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "log_search",
            "description": "Search CloudWatch Logs for a pattern across one or more log groups. Returns matching log lines.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "log_group": {
                            "type": "string",
                            "description": "CloudWatch log group name or prefix",
                        },
                        "filter_pattern": {
                            "type": "string",
                            "description": "CloudWatch Logs filter pattern (e.g. 'ERROR', '?Exception ?Timeout')",
                        },
                        "minutes_ago": {
                            "type": "integer",
                            "description": "How many minutes back to search (default 30)",
                        },
                    },
                    "required": ["log_group", "filter_pattern"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "run_ssm_command",
            "description": "Execute a shell command on an EC2 instance via AWS Systems Manager. Returns stdout/stderr.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "instance_id": {
                            "type": "string",
                            "description": "EC2 instance ID",
                        },
                        "command": {
                            "type": "string",
                            "description": "Shell command to execute",
                        },
                    },
                    "required": ["instance_id", "command"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "describe_network",
            "description": "Describe VPC networking config: security groups, NACLs, route tables, and subnets for a resource.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "resource_id": {
                            "type": "string",
                            "description": "AWS resource ID (instance, ENI, subnet, etc.)",
                        },
                    },
                    "required": ["resource_id"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "get_iam_policy",
            "description": "Retrieve the effective IAM policies for a role or user, including inline and attached policies.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "principal": {
                            "type": "string",
                            "description": "IAM role name or user ARN",
                        },
                    },
                    "required": ["principal"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "run_sql_query",
            "description": "Execute a read-only SQL query against an RDS instance via the Data API.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "cluster_arn": {
                            "type": "string",
                            "description": "RDS cluster ARN",
                        },
                        "database": {
                            "type": "string",
                            "description": "Database name",
                        },
                        "sql": {
                            "type": "string",
                            "description": "SQL query (SELECT only)",
                        },
                    },
                    "required": ["cluster_arn", "database", "sql"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "retrieve_runbook",
            "description": "Search the runbook knowledge base for relevant incident response procedures. Uses TF-IDF retrieval.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Incident description or symptoms to search for",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Number of runbooks to return (default 3)",
                        },
                    },
                    "required": ["query"],
                }
            },
        }
    },
]


def execute_tool(tool_name: str, tool_input: dict) -> dict:
    """Execute a tool and return the result. Uses mock data for demo."""
    executors = {
        "cloudwatch_query": _mock_cloudwatch,
        "log_search": _mock_log_search,
        "run_ssm_command": _mock_ssm,
        "describe_network": _mock_network,
        "get_iam_policy": _mock_iam,
        "run_sql_query": _mock_sql,
        "retrieve_runbook": _exec_retrieve_runbook,
    }
    executor = executors.get(tool_name)
    if not executor:
        return {"error": f"Unknown tool: {tool_name}"}
    try:
        return executor(tool_input)
    except Exception as e:
        return {"error": str(e)}


def _mock_cloudwatch(inp: dict) -> dict:
    now = datetime.now(timezone.utc)
    period = inp.get("period_minutes", 60)
    metric = inp.get("metric_name", "Unknown")
    datapoints = []
    for i in range(6):
        ts = now - timedelta(minutes=period - i * (period // 6))
        if "CPU" in metric:
            val = random.uniform(75, 98)
        elif "Connection" in metric:
            val = random.uniform(80, 150)
        elif "Throttle" in metric:
            val = random.uniform(10, 500)
        elif "Duration" in metric:
            val = random.uniform(5000, 29000)
        elif "Error" in metric or "5xx" in metric.lower():
            val = random.uniform(50, 300)
        else:
            val = random.uniform(10, 90)
        datapoints.append({
            "timestamp": ts.isoformat(),
            "value": round(val, 2),
            "unit": "Percent" if "Percent" in metric or "CPU" in metric else "Count",
        })
    return {
        "namespace": inp.get("namespace", "AWS/EC2"),
        "metric_name": metric,
        "datapoints": datapoints,
        "status": "ok",
    }


def _mock_log_search(inp: dict) -> dict:
    pattern = inp.get("filter_pattern", "ERROR")
    log_group = inp.get("log_group", "/aws/lambda/unknown")
    now = datetime.now(timezone.utc)
    sample_errors = [
        f"ERROR: Connection refused to downstream service at 10.0.1.42:5432",
        f"FATAL: too many connections for role \"appuser\" — max 100",
        f"TimeoutError: Task timed out after 29000ms",
        f"HTTP 503 Service Unavailable from upstream target",
        f"OutOfMemoryError: Container killed (OOMKilled) — limit 512MB",
        f"ERROR: AccessDenied — sts:AssumeRole on arn:aws:iam::123456789012:role/AppRole",
    ]
    events = []
    for i, msg in enumerate(random.sample(sample_errors, min(3, len(sample_errors)))):
        events.append({
            "timestamp": (now - timedelta(minutes=random.randint(1, 30))).isoformat(),
            "message": msg,
            "logStream": f"stream-{random.randint(1000,9999)}",
        })
    return {
        "log_group": log_group,
        "filter_pattern": pattern,
        "events_found": len(events),
        "events": events,
    }


def _mock_ssm(inp: dict) -> dict:
    command = inp.get("command", "uptime")
    if "top" in command:
        output = (
            "top - 14:32:01 up 45 days, 3:21, 0 users\n"
            "Tasks: 142 total, 3 running, 139 sleeping\n"
            "%Cpu(s): 94.2 us, 3.1 sy, 0.0 ni, 2.7 id\n"
            "MiB Mem: 7862.4 total, 312.1 free, 6891.2 used, 659.1 buff/cache\n\n"
            "  PID USER      PR  NI    VIRT    RES    SHR S  %CPU %MEM COMMAND\n"
            " 2847 appuser   20   0 4521312 3.2g   1024 R  89.3 41.7 java\n"
            " 1203 root      20   0  512340 128m  12340 S   4.2  1.6 containerd\n"
        )
    elif "df" in command:
        output = (
            "Filesystem      Size  Used Avail Use% Mounted on\n"
            "/dev/xvda1       50G   47G  3.0G  94% /\n"
            "/dev/xvdf       200G  180G   20G  90% /data\n"
        )
    else:
        output = f"Command executed: {command}\nExit code: 0"
    return {
        "instance_id": inp.get("instance_id", "i-unknown"),
        "status": "Success",
        "stdout": output,
        "stderr": "",
    }


def _mock_network(inp: dict) -> dict:
    return {
        "resource_id": inp.get("resource_id", "unknown"),
        "vpc_id": "vpc-0a1b2c3d4e5f",
        "subnet_id": "subnet-abc123",
        "security_groups": [
            {
                "group_id": "sg-0123456789",
                "inbound_rules": [
                    {"protocol": "tcp", "port": 443, "source": "0.0.0.0/0"},
                    {"protocol": "tcp", "port": 80, "source": "0.0.0.0/0"},
                ],
                "outbound_rules": [
                    {"protocol": "-1", "port": "all", "destination": "0.0.0.0/0"},
                ],
            }
        ],
        "route_table": {
            "routes": [
                {"destination": "0.0.0.0/0", "target": "igw-abc123"},
                {"destination": "10.0.0.0/16", "target": "local"},
            ]
        },
    }


def _mock_iam(inp: dict) -> dict:
    return {
        "principal": inp.get("principal", "unknown"),
        "attached_policies": [
            {"name": "AmazonS3ReadOnlyAccess", "arn": "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess"},
            {"name": "CloudWatchLogsFullAccess", "arn": "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess"},
        ],
        "inline_policies": [
            {
                "name": "AppCustomPolicy",
                "statement": [
                    {"Effect": "Allow", "Action": ["s3:GetObject"], "Resource": "arn:aws:s3:::app-bucket/*"},
                    {"Effect": "Deny", "Action": ["s3:PutObject"], "Resource": "*"},
                ],
            }
        ],
    }


def _mock_sql(inp: dict) -> dict:
    sql = inp.get("sql", "")
    if "connection" in sql.lower() or "pg_stat" in sql.lower():
        rows = [
            {"state": "active", "count": 42, "application_name": "app-server"},
            {"state": "idle", "count": 55, "application_name": "app-server"},
            {"state": "idle in transaction", "count": 3, "application_name": "migration-job"},
        ]
    else:
        rows = [{"result": "Query executed", "rows_affected": 0}]
    return {
        "database": inp.get("database", "unknown"),
        "rows_returned": len(rows),
        "rows": rows,
    }


def _exec_retrieve_runbook(inp: dict) -> dict:
    from agent.runbooks import retrieve_runbooks
    query = inp.get("query", "")
    top_k = inp.get("top_k", 3)
    results = retrieve_runbooks(query, top_k=top_k)
    return {"query": query, "runbooks_found": len(results), "runbooks": results}
