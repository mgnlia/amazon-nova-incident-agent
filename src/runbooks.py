"""
RAG Runbook Store — in-memory vector similarity search over DevOps runbooks.
Uses cosine similarity on simple TF-IDF-style keyword vectors.
"""
from __future__ import annotations
import math
import re
from dataclasses import dataclass, field
from typing import List


RUNBOOKS: List[dict] = [
    {
        "id": "rb-001",
        "title": "High CPU Usage — EC2 Instance",
        "tags": ["cpu", "ec2", "performance", "high-load"],
        "content": """
## Runbook: High CPU Usage on EC2

### Symptoms
- CPU utilization > 90% for > 5 minutes
- Application response times degraded
- CloudWatch alarm: CPUUtilization

### Diagnosis Steps
1. Check top processes: `ssh ec2-user@<host> 'top -bn1 | head -20'`
2. Identify runaway process: `ps aux --sort=-%cpu | head -10`
3. Check application logs: `journalctl -u app --since '10 min ago'`
4. Review recent deployments in deployment log

### Remediation
1. **Auto-scale**: Trigger ASG scale-out if CPU > 85% sustained
   - `aws autoscaling set-desired-capacity --auto-scaling-group-name <asg> --desired-capacity <n+1>`
2. **Kill runaway process** (if identified):
   - `kill -15 <pid>` (graceful), then `kill -9 <pid>` if needed
3. **Restart service** if process is application:
   - `systemctl restart app`
4. **Rollback deployment** if triggered by recent deploy

### Escalation
- If CPU stays > 95% after scale-out: page on-call SRE
- If multiple instances affected: declare incident P1
""",
    },
    {
        "id": "rb-002",
        "title": "Database Connection Pool Exhausted",
        "tags": ["database", "rds", "postgres", "mysql", "connection", "pool"],
        "content": """
## Runbook: Database Connection Pool Exhausted

### Symptoms
- Error: "too many connections" or "connection pool exhausted"
- Application 500 errors on DB queries
- RDS CloudWatch: DatabaseConnections at max_connections

### Diagnosis Steps
1. Check current connections: `SELECT count(*) FROM pg_stat_activity;`
2. Identify long-running queries: 
   `SELECT pid, now() - pg_stat_activity.query_start AS duration, query, state FROM pg_stat_activity WHERE state != 'idle' ORDER BY duration DESC;`
3. Check connection pool config in app settings
4. Review recent traffic spike in ALB metrics

### Remediation
1. **Kill idle connections**:
   `SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle' AND query_start < now() - interval '10 minutes';`
2. **Reduce pool size** in app config and restart
3. **Scale RDS instance** if consistently at limit:
   - `aws rds modify-db-instance --db-instance-identifier <id> --db-instance-class db.r5.2xlarge --apply-immediately`
4. **Enable PgBouncer** connection pooler if not already active

### Escalation
- If data loss suspected: page DBA immediately
- If RDS unavailable: activate RDS failover to read replica
""",
    },
    {
        "id": "rb-003",
        "title": "Memory Exhaustion / OOM Kill",
        "tags": ["memory", "oom", "out-of-memory", "ram", "swap"],
        "content": """
## Runbook: Memory Exhaustion / OOM Kill

### Symptoms
- OOM killer activated in dmesg
- Process killed unexpectedly
- CloudWatch: MemoryUtilization > 95%
- Application crashes with exit code 137

### Diagnosis Steps
1. Check OOM events: `dmesg | grep -i 'oom\|killed'`
2. Current memory: `free -h && cat /proc/meminfo`
3. Top memory consumers: `ps aux --sort=-%mem | head -15`
4. Check for memory leak: monitor process RSS over time

### Remediation
1. **Immediate**: Restart affected service
   - `systemctl restart <service>`
2. **Add swap** (temporary):
   - `fallocate -l 4G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile`
3. **Scale vertically**: Upgrade instance type
   - Stop instance, change type, restart
4. **Fix memory leak**: Identify and deploy patch

### Escalation
- If data corruption suspected: halt writes, page on-call
""",
    },
    {
        "id": "rb-004",
        "title": "Service Unavailable / Health Check Failing",
        "tags": ["health", "service", "down", "503", "502", "unavailable", "alb", "load-balancer"],
        "content": """
## Runbook: Service Unavailable / Health Check Failing

### Symptoms
- ALB health checks failing
- HTTP 502/503 responses
- PagerDuty: Service health check alert

### Diagnosis Steps
1. Check ALB target health: `aws elbv2 describe-target-health --target-group-arn <arn>`
2. SSH to instance and check service: `systemctl status app`
3. Check application logs: `journalctl -u app -n 100`
4. Verify port binding: `ss -tlnp | grep <port>`
5. Check disk space: `df -h` (full disk can cause failures)

### Remediation
1. **Restart service**: `systemctl restart app`
2. **Check and free disk**: `du -sh /* | sort -rh | head -10`
3. **Redeploy last known good**: Roll back to previous task definition (ECS) or AMI
4. **Drain and replace instance**: Remove from ALB, terminate, let ASG replace

### Escalation
- If all instances failing: P1 incident, page entire on-call rotation
""",
    },
    {
        "id": "rb-005",
        "title": "Disk Space Critical",
        "tags": ["disk", "storage", "space", "full", "ebs", "volume"],
        "content": """
## Runbook: Disk Space Critical

### Symptoms
- CloudWatch: DiskSpaceUtilization > 85%
- Write errors in application logs
- df -h shows > 90% used

### Diagnosis Steps
1. Find large files: `du -sh /* 2>/dev/null | sort -rh | head -20`
2. Check log directory: `du -sh /var/log/*`
3. Check for core dumps: `find / -name 'core.*' 2>/dev/null`
4. Check Docker images if applicable: `docker system df`

### Remediation
1. **Clean logs**: `journalctl --vacuum-time=7d`
2. **Remove old files**: `find /tmp -mtime +7 -delete`
3. **Docker cleanup**: `docker system prune -af`
4. **Expand EBS volume**:
   - `aws ec2 modify-volume --volume-id <vol-id> --size <new-size>`
   - Then: `resize2fs /dev/xvda1`

### Escalation
- If disk > 95% and cannot free space: emergency EBS expansion
""",
    },
    {
        "id": "rb-006",
        "title": "Network Latency / Packet Loss",
        "tags": ["network", "latency", "packet-loss", "connectivity", "vpc", "timeout"],
        "content": """
## Runbook: Network Latency / Packet Loss

### Symptoms
- Increased API response times
- Timeout errors between services
- CloudWatch: NetworkIn/Out anomaly

### Diagnosis Steps
1. Ping test: `ping -c 20 <target>` — check packet loss
2. Traceroute: `traceroute <target>`
3. Check security groups: allow required ports
4. Check VPC flow logs for drops
5. Verify NAT gateway / IGW health

### Remediation
1. **Security group**: Add missing ingress/egress rules
2. **Route table**: Verify correct routes
3. **Replace NAT gateway** if unhealthy
4. **Contact AWS support** if carrier-level issue

### Escalation
- Cross-AZ latency > 5ms: escalate to AWS support
""",
    },
]


@dataclass
class RunbookMatch:
    runbook_id: str
    title: str
    score: float
    content: str
    tags: List[str]


def _tokenize(text: str) -> dict[str, int]:
    """Simple word frequency tokenizer."""
    words = re.findall(r'\b[a-z0-9]+\b', text.lower())
    freq: dict[str, int] = {}
    for w in words:
        if len(w) > 2:  # skip tiny words
            freq[w] = freq.get(w, 0) + 1
    return freq


def _cosine_similarity(a: dict[str, int], b: dict[str, int]) -> float:
    """Compute cosine similarity between two frequency dicts."""
    if not a or not b:
        return 0.0
    dot = sum(a.get(k, 0) * v for k, v in b.items())
    mag_a = math.sqrt(sum(v * v for v in a.values()))
    mag_b = math.sqrt(sum(v * v for v in b.values()))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


# Pre-compute runbook vectors
_RUNBOOK_VECTORS = []
for rb in RUNBOOKS:
    text = f"{rb['title']} {' '.join(rb['tags'])} {rb['content']}"
    _RUNBOOK_VECTORS.append(_tokenize(text))


def retrieve_runbooks(query: str, top_k: int = 2) -> List[RunbookMatch]:
    """Retrieve top-k runbooks most relevant to the query."""
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
