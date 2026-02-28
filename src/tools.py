"""
Infrastructure remediation tools available to the Nova agent.
In production these would call real AWS APIs. Here they are mocked
with realistic responses and simulated delays.
"""
from __future__ import annotations
import json
import random
import time
from typing import Any


# Tool definitions in Bedrock converse format
TOOL_DEFINITIONS = [
    {
        "toolSpec": {
            "name": "get_cloudwatch_metrics",
            "description": "Retrieve CloudWatch metrics for a given resource over the past N minutes.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "resource_id": {"type": "string", "description": "EC2 instance ID, RDS identifier, etc."},
                        "metric_name": {"type": "string", "description": "CloudWatch metric name (e.g. CPUUtilization)"},
                        "period_minutes": {"type": "integer", "description": "How many minutes back to query", "default": 30},
                    },
                    "required": ["resource_id", "metric_name"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "get_application_logs",
            "description": "Fetch recent application logs from CloudWatch Logs or the instance.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "resource_id": {"type": "string"},
                        "log_group": {"type": "string", "description": "CloudWatch log group name"},
                        "lines": {"type": "integer", "description": "Number of recent log lines", "default": 50},
                    },
                    "required": ["resource_id"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "restart_service",
            "description": "Restart a service on an EC2 instance or ECS task.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "resource_id": {"type": "string"},
                        "service_name": {"type": "string", "description": "Service name (e.g. 'app', 'nginx')"},
                    },
                    "required": ["resource_id", "service_name"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "scale_asg",
            "description": "Scale an Auto Scaling Group to a new desired capacity.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "asg_name": {"type": "string"},
                        "desired_capacity": {"type": "integer"},
                    },
                    "required": ["asg_name", "desired_capacity"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "kill_process",
            "description": "Kill a runaway process on an EC2 instance by PID or name.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "resource_id": {"type": "string"},
                        "pid": {"type": "integer", "description": "Process ID to kill"},
                        "process_name": {"type": "string", "description": "Process name (alternative to PID)"},
                    },
                    "required": ["resource_id"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "expand_ebs_volume",
            "description": "Expand an EBS volume attached to an EC2 instance.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "volume_id": {"type": "string"},
                        "new_size_gb": {"type": "integer"},
                    },
                    "required": ["volume_id", "new_size_gb"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "terminate_db_connections",
            "description": "Terminate idle or long-running database connections.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "db_identifier": {"type": "string"},
                        "idle_threshold_minutes": {"type": "integer", "default": 10},
                    },
                    "required": ["db_identifier"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "create_incident_report",
            "description": "Create a final incident report summarizing the issue, diagnosis, and remediation taken.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "incident_id": {"type": "string"},
                        "severity": {"type": "string", "enum": ["P1", "P2", "P3", "P4"]},
                        "summary": {"type": "string"},
                        "root_cause": {"type": "string"},
                        "actions_taken": {"type": "array", "items": {"type": "string"}},
                        "resolution_status": {"type": "string", "enum": ["resolved", "mitigated", "escalated"]},
                        "follow_up": {"type": "string"},
                    },
                    "required": ["incident_id", "severity", "summary", "root_cause", "actions_taken", "resolution_status"],
                }
            },
        }
    },
]


def execute_tool(tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    """Execute a tool and return the result. All tools are mocked."""
    
    if tool_name == "get_cloudwatch_metrics":
        resource_id = tool_input["resource_id"]
        metric = tool_input["metric_name"]
        period = tool_input.get("period_minutes", 30)
        
        # Generate realistic metric data based on metric name
        if "CPU" in metric:
            current = random.uniform(88, 97)
            avg = random.uniform(82, 93)
            return {
                "resource_id": resource_id,
                "metric": metric,
                "period_minutes": period,
                "current_value": round(current, 1),
                "average": round(avg, 1),
                "maximum": round(min(current + 5, 100), 1),
                "unit": "Percent",
                "datapoints": [round(random.uniform(75, 97), 1) for _ in range(min(period, 10))],
                "alarm_threshold": 85,
                "alarm_state": "ALARM",
            }
        elif "Memory" in metric or "memory" in metric:
            current = random.uniform(91, 98)
            return {
                "resource_id": resource_id,
                "metric": metric,
                "period_minutes": period,
                "current_value": round(current, 1),
                "average": round(current - 5, 1),
                "unit": "Percent",
                "alarm_state": "ALARM",
            }
        elif "DatabaseConnections" in metric:
            return {
                "resource_id": resource_id,
                "metric": metric,
                "current_value": 498,
                "maximum_allowed": 500,
                "unit": "Count",
                "alarm_state": "ALARM",
            }
        elif "Disk" in metric:
            return {
                "resource_id": resource_id,
                "metric": metric,
                "current_value": 92.3,
                "unit": "Percent",
                "alarm_state": "ALARM",
            }
        else:
            return {
                "resource_id": resource_id,
                "metric": metric,
                "current_value": random.uniform(50, 90),
                "unit": "Count",
                "alarm_state": "OK",
            }

    elif tool_name == "get_application_logs":
        resource_id = tool_input["resource_id"]
        lines = tool_input.get("lines", 50)
        return {
            "resource_id": resource_id,
            "log_lines": [
                "[2026-02-28 10:15:32] ERROR: Request timeout after 30s",
                "[2026-02-28 10:15:33] WARN: Connection pool at 95% capacity",
                "[2026-02-28 10:15:34] ERROR: Failed to acquire DB connection",
                "[2026-02-28 10:15:35] INFO: CPU throttling detected",
                "[2026-02-28 10:15:36] ERROR: Out of memory, GC overhead limit exceeded",
                "[2026-02-28 10:15:37] WARN: Heap usage: 7.8GB / 8GB",
                "[2026-02-28 10:15:38] ERROR: Worker process 18423 killed by OOM",
            ][:lines],
            "log_group": tool_input.get("log_group", f"/app/{resource_id}"),
            "total_errors_last_5min": random.randint(45, 120),
        }

    elif tool_name == "restart_service":
        resource_id = tool_input["resource_id"]
        service = tool_input["service_name"]
        time.sleep(0.1)  # simulate latency
        return {
            "success": True,
            "resource_id": resource_id,
            "service": service,
            "action": "restart",
            "new_pid": random.randint(10000, 99999),
            "status": "active (running)",
            "message": f"Service '{service}' restarted successfully on {resource_id}",
        }

    elif tool_name == "scale_asg":
        asg_name = tool_input["asg_name"]
        desired = tool_input["desired_capacity"]
        return {
            "success": True,
            "asg_name": asg_name,
            "previous_desired": desired - 2,
            "new_desired": desired,
            "estimated_time_seconds": 90,
            "message": f"ASG '{asg_name}' scaling to {desired} instances. New instances launching.",
        }

    elif tool_name == "kill_process":
        resource_id = tool_input["resource_id"]
        pid = tool_input.get("pid", random.randint(1000, 50000))
        pname = tool_input.get("process_name", "unknown")
        return {
            "success": True,
            "resource_id": resource_id,
            "pid": pid,
            "process_name": pname,
            "signal": "SIGTERM",
            "message": f"Process {pid} ({pname}) terminated on {resource_id}",
        }

    elif tool_name == "expand_ebs_volume":
        vol_id = tool_input["volume_id"]
        new_size = tool_input["new_size_gb"]
        return {
            "success": True,
            "volume_id": vol_id,
            "old_size_gb": new_size - 100,
            "new_size_gb": new_size,
            "state": "modifying",
            "estimated_completion_minutes": 5,
            "message": f"EBS volume {vol_id} expansion to {new_size}GB initiated.",
        }

    elif tool_name == "terminate_db_connections":
        db_id = tool_input["db_identifier"]
        threshold = tool_input.get("idle_threshold_minutes", 10)
        terminated = random.randint(45, 120)
        return {
            "success": True,
            "db_identifier": db_id,
            "connections_terminated": terminated,
            "idle_threshold_minutes": threshold,
            "current_connections_after": random.randint(50, 150),
            "message": f"Terminated {terminated} idle connections on {db_id}",
        }

    elif tool_name == "create_incident_report":
        return {
            "success": True,
            "incident_id": tool_input["incident_id"],
            "report_url": f"https://incidents.internal/reports/{tool_input['incident_id']}",
            "created_at": "2026-02-28T10:30:00Z",
            "severity": tool_input["severity"],
            "resolution_status": tool_input["resolution_status"],
            "summary": tool_input["summary"],
            "root_cause": tool_input["root_cause"],
            "actions_taken": tool_input["actions_taken"],
            "follow_up": tool_input.get("follow_up", "Monitor for 24h"),
            "message": "Incident report created and sent to stakeholders",
        }

    else:
        return {"error": f"Unknown tool: {tool_name}"}
