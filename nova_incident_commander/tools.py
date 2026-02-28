"""
Infrastructure tools available to the Nova agent via Bedrock tool use.
Each tool has a Bedrock toolSpec definition and a mock executor.
Real AWS calls can be wired in by setting AGENT_MODE=bedrock.
"""
from __future__ import annotations

import random
import uuid
from typing import Any

# ── Bedrock toolConfig definitions ────────────────────────────────────────────

TOOL_SPECS = [
    {
        "toolSpec": {
            "name": "check_service_status",
            "description": (
                "Check the current health/status of a service or EC2 instance. "
                "Returns running state, uptime, and recent restart count."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "service": {
                            "type": "string",
                            "description": "Service name or EC2 instance ID (e.g. 'api-server', 'i-0abc123')",
                        }
                    },
                    "required": ["service"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "restart_service",
            "description": (
                "Restart a service on an EC2 instance or ECS task. "
                "Use when service is crashed, OOM-killed, or in a bad state."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "service": {
                            "type": "string",
                            "description": "Service name to restart (e.g. 'app', 'nginx', 'worker')",
                        },
                        "resource_id": {
                            "type": "string",
                            "description": "EC2 instance ID or ECS cluster/service ARN",
                        },
                    },
                    "required": ["service", "resource_id"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "scale_asg",
            "description": (
                "Scale an Auto Scaling Group to a new desired capacity. "
                "Use to add capacity during high load or replace unhealthy instances."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "group": {
                            "type": "string",
                            "description": "Auto Scaling Group name",
                        },
                        "count": {
                            "type": "integer",
                            "description": "New desired capacity (number of instances)",
                            "minimum": 1,
                            "maximum": 50,
                        },
                    },
                    "required": ["group", "count"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "query_logs",
            "description": (
                "Query recent application or system logs for a service. "
                "Returns the most recent log lines including errors and warnings."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "service": {
                            "type": "string",
                            "description": "Service name or log group",
                        },
                        "timerange": {
                            "type": "string",
                            "description": "Time range to query (e.g. '5m', '15m', '1h')",
                        },
                    },
                    "required": ["service", "timerange"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "check_cloudwatch_metrics",
            "description": (
                "Retrieve CloudWatch metrics for a resource. "
                "Use to get CPU, memory, disk, connection count, or any other metric."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "resource_id": {
                            "type": "string",
                            "description": "Resource ID (EC2 instance, RDS identifier, etc.)",
                        },
                        "metric_name": {
                            "type": "string",
                            "description": "CloudWatch metric name (e.g. CPUUtilization, MemoryUtilization, DatabaseConnections)",
                        },
                    },
                    "required": ["resource_id", "metric_name"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "terminate_db_connections",
            "description": (
                "Terminate idle or long-running database connections to free up the connection pool. "
                "Use when DatabaseConnections metric is near max_connections."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "db_identifier": {
                            "type": "string",
                            "description": "RDS DB instance identifier",
                        },
                        "idle_threshold_minutes": {
                            "type": "integer",
                            "description": "Terminate connections idle longer than this many minutes",
                            "default": 10,
                        },
                    },
                    "required": ["db_identifier"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "expand_ebs_volume",
            "description": (
                "Expand an EBS volume to increase disk space. "
                "Use when DiskSpaceUtilization is critically high."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "volume_id": {
                            "type": "string",
                            "description": "EBS volume ID (e.g. vol-0abc123)",
                        },
                        "new_size_gb": {
                            "type": "integer",
                            "description": "New volume size in GB",
                            "minimum": 1,
                            "maximum": 16384,
                        },
                    },
                    "required": ["volume_id", "new_size_gb"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "create_ticket",
            "description": (
                "Create an incident ticket in the ticketing system (PagerDuty/Jira). "
                "Use for escalation, follow-up actions, or when human intervention is needed."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Ticket title/summary",
                        },
                        "description": {
                            "type": "string",
                            "description": "Detailed description of the issue and actions taken",
                        },
                        "severity": {
                            "type": "string",
                            "enum": ["P1", "P2", "P3", "P4"],
                            "description": "Ticket severity/priority",
                        },
                    },
                    "required": ["title", "description", "severity"],
                }
            },
        }
    },
]

TOOL_CONFIG = {"tools": TOOL_SPECS}


# ── Mock tool executors ────────────────────────────────────────────────────────

def execute_tool(tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    """Execute a tool call and return its result. All tools are mocked realistically."""

    if tool_name == "check_service_status":
        service = tool_input["service"]
        # Simulate unhealthy service
        is_healthy = random.random() > 0.4
        return {
            "service": service,
            "status": "healthy" if is_healthy else "unhealthy",
            "state": "running" if is_healthy else "failed",
            "uptime_seconds": random.randint(60, 86400) if is_healthy else 0,
            "restart_count_24h": random.randint(0, 2) if is_healthy else random.randint(5, 20),
            "last_restart": "2026-02-28T09:45:00Z",
            "pid": random.randint(1000, 60000) if is_healthy else None,
        }

    elif tool_name == "restart_service":
        service = tool_input["service"]
        resource_id = tool_input["resource_id"]
        return {
            "success": True,
            "service": service,
            "resource_id": resource_id,
            "action": "restarted",
            "new_pid": random.randint(10000, 99999),
            "status": "active (running)",
            "message": f"Service '{service}' successfully restarted on {resource_id}",
            "duration_ms": random.randint(800, 3000),
        }

    elif tool_name == "scale_asg":
        group = tool_input["group"]
        count = tool_input["count"]
        prev = max(1, count - random.randint(1, 3))
        return {
            "success": True,
            "asg_name": group,
            "previous_desired": prev,
            "new_desired": count,
            "instances_launching": count - prev,
            "estimated_ready_seconds": 90,
            "message": f"ASG '{group}' scaling from {prev} to {count} instances. New instances launching.",
        }

    elif tool_name == "query_logs":
        service = tool_input["service"]
        timerange = tool_input.get("timerange", "5m")
        return {
            "service": service,
            "timerange": timerange,
            "error_count": random.randint(20, 150),
            "log_lines": [
                f"[2026-02-28 10:12:01] ERROR {service}: Connection timeout after 30s",
                f"[2026-02-28 10:12:03] WARN  {service}: Retry attempt 3/3 failed",
                f"[2026-02-28 10:12:05] ERROR {service}: Out of memory — heap size 7.9GB/8GB",
                f"[2026-02-28 10:12:07] ERROR {service}: Worker process 18423 killed (OOM)",
                f"[2026-02-28 10:12:09] WARN  {service}: CPU throttling active (95% utilization)",
                f"[2026-02-28 10:12:11] ERROR {service}: DB connection pool exhausted (500/500)",
                f"[2026-02-28 10:12:13] ERROR {service}: Health check failed — returning 503",
            ],
        }

    elif tool_name == "check_cloudwatch_metrics":
        resource_id = tool_input["resource_id"]
        metric = tool_input["metric_name"]
        if "CPU" in metric:
            val = random.uniform(87, 97)
            return {"resource_id": resource_id, "metric": metric,
                    "current": round(val, 1), "average_5m": round(val - 5, 1),
                    "unit": "Percent", "alarm_state": "ALARM", "threshold": 85}
        elif "Memory" in metric:
            val = random.uniform(90, 98)
            return {"resource_id": resource_id, "metric": metric,
                    "current": round(val, 1), "unit": "Percent",
                    "alarm_state": "ALARM", "threshold": 85}
        elif "DatabaseConnections" in metric:
            return {"resource_id": resource_id, "metric": metric,
                    "current": 498, "max_connections": 500,
                    "unit": "Count", "alarm_state": "ALARM"}
        elif "Disk" in metric:
            return {"resource_id": resource_id, "metric": metric,
                    "current": 92.3, "unit": "Percent", "alarm_state": "ALARM"}
        elif "HealthyHostCount" in metric:
            return {"resource_id": resource_id, "metric": metric,
                    "current": random.randint(0, 2), "desired": 3,
                    "unit": "Count", "alarm_state": "ALARM"}
        else:
            return {"resource_id": resource_id, "metric": metric,
                    "current": round(random.uniform(40, 90), 1),
                    "unit": "Count", "alarm_state": "OK"}

    elif tool_name == "terminate_db_connections":
        db_id = tool_input["db_identifier"]
        threshold = tool_input.get("idle_threshold_minutes", 10)
        terminated = random.randint(40, 130)
        return {
            "success": True,
            "db_identifier": db_id,
            "connections_terminated": terminated,
            "idle_threshold_minutes": threshold,
            "connections_remaining": random.randint(30, 100),
            "message": f"Terminated {terminated} idle connections on {db_id}",
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
            "message": f"EBS volume {vol_id} expansion to {new_size}GB initiated successfully.",
        }

    elif tool_name == "create_ticket":
        ticket_id = f"INC-{random.randint(10000, 99999)}"
        return {
            "success": True,
            "ticket_id": ticket_id,
            "title": tool_input["title"],
            "severity": tool_input.get("severity", "P3"),
            "url": f"https://incidents.internal/tickets/{ticket_id}",
            "assigned_to": "on-call-sre",
            "message": f"Ticket {ticket_id} created and assigned to on-call SRE",
        }

    else:
        return {"error": f"Unknown tool: {tool_name}", "tool_name": tool_name}
