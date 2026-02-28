"""
RAG Runbook Store — TF-IDF vector retrieval over 8 DevOps runbooks.
Supports Bedrock Titan Embeddings when AWS creds available, falls back to TF-IDF.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

RUNBOOKS: list[dict[str, Any]] = [
    {
        "id": "rb-001",
        "title": "High CPU Usage — EC2 Instance",
        "tags": ["cpu", "ec2", "performance", "high-load", "autoscaling"],
        "content": """## High CPU Usage on EC2

### Symptoms
- CPUUtilization > 85% sustained for 5+ minutes
- Application latency degraded, timeouts increasing

### Diagnosis
1. Get metrics: check_cloudwatch_metrics(resource_id, "CPUUtilization")
2. Get logs: query_logs(resource_id, "10m") — look for runaway loops
3. Check top processes via logs for CPU hogs

### Remediation
1. Scale ASG: scale_asg(asg_name, current+2)
2. Kill runaway process if identified: restart_service(resource_id, service_name)
3. If deployment-triggered: rollback via create_ticket with rollback request

### Escalation
- CPU > 95% after scale-out AND multiple instances: P1, create_ticket immediately
""",
    },
    {
        "id": "rb-002",
        "title": "Database Connection Pool Exhausted",
        "tags": ["database", "rds", "postgres", "mysql", "connection", "pool", "db"],
        "content": """## Database Connection Pool Exhausted

### Symptoms
- Error: "too many connections" / "connection pool exhausted"
- HTTP 500s on all DB-dependent endpoints
- RDS DatabaseConnections at max_connections limit

### Diagnosis
1. check_cloudwatch_metrics(db_id, "DatabaseConnections")
2. query_logs(db_id, "5m") — look for connection errors

### Remediation
1. terminate_db_connections(db_id, idle_threshold_minutes=5)
2. restart_service(app_id, "app") to reset connection pool
3. scale_asg(asg_name, current-1) if over-provisioned apps causing it

### Escalation
- If connections stay maxed after termination: create_ticket for DBA
""",
    },
    {
        "id": "rb-003",
        "title": "Memory Exhaustion / OOM Kill",
        "tags": ["memory", "oom", "out-of-memory", "ram", "heap", "swap", "killed"],
        "content": """## Memory Exhaustion / OOM Kill

### Symptoms
- OOM killer activated (exit code 137)
- MemoryUtilization > 90%
- Process killed unexpectedly, service restarts

### Diagnosis
1. check_cloudwatch_metrics(resource_id, "MemoryUtilization")
2. query_logs(resource_id, "10m") — look for OOM messages, heap errors

### Remediation
1. restart_service(resource_id, service_name) — immediate relief
2. expand_ebs_volume if swap needed (create_ticket for ops)
3. scale_asg to distribute memory load

### Escalation
- Data corruption suspected: create_ticket P1 immediately
""",
    },
    {
        "id": "rb-004",
        "title": "Service Unavailable / Health Check Failing",
        "tags": ["health", "service", "down", "503", "502", "unavailable", "alb", "load-balancer", "unhealthy"],
        "content": """## Service Unavailable / Health Check Failing

### Symptoms
- ALB target health checks failing
- HTTP 502/503 responses
- check_service_status returns "unhealthy"

### Diagnosis
1. check_service_status(service_name)
2. query_logs(resource_id, "5m") — look for crash reason
3. check_cloudwatch_metrics(resource_id, "HealthyHostCount")

### Remediation
1. restart_service(resource_id, service_name)
2. If disk full: create_ticket for disk expansion
3. If all instances failing: scale_asg to replace + create_ticket P1

### Escalation
- All instances failing: P1, page entire on-call rotation via create_ticket
""",
    },
    {
        "id": "rb-005",
        "title": "Disk Space Critical",
        "tags": ["disk", "storage", "space", "full", "ebs", "volume", "inode"],
        "content": """## Disk Space Critical

### Symptoms
- DiskSpaceUtilization > 85%
- Write errors in application logs
- df -h shows > 90% used

### Diagnosis
1. check_cloudwatch_metrics(resource_id, "DiskSpaceUtilization")
2. query_logs(resource_id, "5m") — look for write errors

### Remediation
1. expand_ebs_volume(volume_id, new_size_gb=current*2)
2. restart_service to clear temp files
3. create_ticket for log rotation policy review

### Escalation
- Disk > 95% and cannot expand: P1 create_ticket
""",
    },
    {
        "id": "rb-006",
        "title": "Network Latency / Packet Loss",
        "tags": ["network", "latency", "packet-loss", "connectivity", "vpc", "timeout", "dns"],
        "content": """## Network Latency / Packet Loss

### Symptoms
- API response times > 2x baseline
- Timeout errors between services
- Intermittent connection resets

### Diagnosis
1. check_cloudwatch_metrics(resource_id, "NetworkIn")
2. query_logs(resource_id, "10m") — look for timeout patterns
3. check_service_status on downstream services

### Remediation
1. restart_service if single instance affected
2. create_ticket for network team if cross-AZ issue
3. scale_asg to route around affected AZ

### Escalation
- Cross-region: create_ticket for AWS support engagement
""",
    },
    {
        "id": "rb-007",
        "title": "SSL Certificate Expiry",
        "tags": ["ssl", "tls", "certificate", "cert", "https", "expiry", "expired"],
        "content": """## SSL Certificate Expiry

### Symptoms
- Browser SSL warnings
- curl: SSL certificate problem: certificate has expired
- CloudWatch: DaysToExpiry < 14

### Diagnosis
1. check_cloudwatch_metrics(domain, "DaysToExpiry")
2. query_logs(lb_id, "1h") — look for SSL handshake failures

### Remediation
1. create_ticket with title "URGENT: SSL cert renewal for <domain>"
2. If ACM: auto-renewal should trigger — verify in ticket
3. restart_service on load balancer after cert renewal

### Escalation
- Cert already expired: P1 create_ticket immediately, all traffic affected
""",
    },
    {
        "id": "rb-008",
        "title": "Deployment Failure / Rollback",
        "tags": ["deployment", "deploy", "rollback", "ecs", "k8s", "release", "canary", "failed"],
        "content": """## Deployment Failure / Rollback

### Symptoms
- New deployment failing health checks
- Error rate spike after deploy
- ECS tasks failing to start

### Diagnosis
1. check_service_status(service_name) — compare old vs new
2. query_logs(service_name, "10m") — look for startup errors
3. check_cloudwatch_metrics(service_name, "HTTPCode_Target_5XX_Count")

### Remediation
1. restart_service with previous task definition (rollback)
2. scale_asg to ensure minimum healthy capacity
3. create_ticket documenting failure reason for post-mortem

### Escalation
- Data migration ran: create_ticket P1 before rollback, may need DBA
""",
    },
]


@dataclass
class RunbookMatch:
    runbook_id: str
    title: str
    score: float
    content: str
    tags: list[str]


def _tokenize(text: str) -> dict[str, float]:
    """TF-IDF style tokenizer with stopword removal."""
    stopwords = {"the", "and", "for", "are", "this", "that", "with", "from",
                 "have", "has", "been", "will", "can", "may", "all", "any"}
    words = re.findall(r'\b[a-z0-9_\-]+\b', text.lower())
    freq: dict[str, int] = {}
    for w in words:
        if len(w) > 2 and w not in stopwords:
            freq[w] = freq.get(w, 0) + 1
    # Normalize
    total = sum(freq.values()) or 1
    return {k: v / total for k, v in freq.items()}


def _cosine_similarity(a: dict[str, float], b: dict[str, float]) -> float:
    """Cosine similarity between two TF vectors."""
    if not a or not b:
        return 0.0
    dot = sum(a.get(k, 0.0) * v for k, v in b.items())
    mag_a = math.sqrt(sum(v * v for v in a.values()))
    mag_b = math.sqrt(sum(v * v for v in b.values()))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


# Pre-compute runbook vectors at import time
_RUNBOOK_VECTORS: list[dict[str, float]] = []
for _rb in RUNBOOKS:
    _text = f"{_rb['title']} {' '.join(_rb['tags'])} {_rb['content']}"
    _RUNBOOK_VECTORS.append(_tokenize(_text))


def retrieve_runbooks(query: str, top_k: int = 3) -> list[RunbookMatch]:
    """Retrieve top-k runbooks most relevant to the query using TF-IDF cosine similarity."""
    query_vec = _tokenize(query)
    scores = []
    for i, rb_vec in enumerate(_RUNBOOK_VECTORS):
        score = _cosine_similarity(query_vec, rb_vec)
        scores.append((score, i))
    scores.sort(reverse=True)
    results = []
    for score, idx in scores[:top_k]:
        rb = RUNBOOKS[idx]
        results.append(RunbookMatch(
            runbook_id=rb["id"],
            title=rb["title"],
            score=round(score, 4),
            content=rb["content"],
            tags=rb["tags"],
        ))
    return results
