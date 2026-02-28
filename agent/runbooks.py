"""
10 built-in DevOps runbooks for incident response.
Each runbook has: id, title, symptoms, steps, tools_needed.
TF-IDF retrieval selects the best-match runbook for a given incident.
"""

from __future__ import annotations
import math
import re
from dataclasses import dataclass, field

RUNBOOKS: list[dict] = [
    {
        "id": "rb-001",
        "title": "High CPU / Memory on EC2",
        "symptoms": "cpu spike memory high utilization ec2 instance performance degraded slow response",
        "steps": [
            "Identify top processes via CloudWatch or SSM RunCommand (top -bn1)",
            "Check for runaway processes or memory leaks",
            "Scale vertically (resize instance) or horizontally (add to ASG)",
            "Set up CloudWatch alarm for future detection",
        ],
        "tools_needed": ["cloudwatch_query", "run_ssm_command"],
    },
    {
        "id": "rb-002",
        "title": "5xx Errors on ALB / API Gateway",
        "symptoms": "5xx 500 502 503 504 error rate load balancer alb api gateway http errors",
        "steps": [
            "Check ALB target group health — identify unhealthy targets",
            "Review backend application logs for exceptions",
            "Verify security group and network ACL rules",
            "Check if backend is overwhelmed — scale if needed",
        ],
        "tools_needed": ["cloudwatch_query", "log_search"],
    },
    {
        "id": "rb-003",
        "title": "Database Connection Exhaustion (RDS)",
        "symptoms": "rds database connection pool exhausted max connections too many connections postgres mysql aurora",
        "steps": [
            "Query RDS DatabaseConnections metric",
            "Identify connection-hogging queries via Performance Insights",
            "Kill idle connections if safe",
            "Increase max_connections or use RDS Proxy for pooling",
        ],
        "tools_needed": ["cloudwatch_query", "run_sql_query"],
    },
    {
        "id": "rb-004",
        "title": "Lambda Throttling / Timeout",
        "symptoms": "lambda throttle timeout duration exceeded concurrency limit invocation error function",
        "steps": [
            "Check Lambda Throttles and Duration metrics",
            "Review reserved/provisioned concurrency settings",
            "Optimize function code or increase timeout",
            "Request concurrency limit increase if needed",
        ],
        "tools_needed": ["cloudwatch_query", "log_search"],
    },
    {
        "id": "rb-005",
        "title": "S3 Access Denied / Bucket Policy Issue",
        "symptoms": "s3 access denied 403 forbidden bucket policy iam permission object storage",
        "steps": [
            "Review bucket policy and IAM role permissions",
            "Check S3 Block Public Access settings",
            "Verify KMS key permissions if using SSE-KMS",
            "Use IAM Policy Simulator to debug",
        ],
        "tools_needed": ["get_iam_policy", "log_search"],
    },
    {
        "id": "rb-006",
        "title": "ECS/EKS Task Crash Loop",
        "symptoms": "ecs eks container crash restart loop task failed oom killed pod backoff",
        "steps": [
            "Check stopped task reasons (ECS) or pod events (EKS)",
            "Review container logs for crash cause",
            "Check resource limits — OOMKilled indicates memory cap too low",
            "Verify health check configuration and startup timing",
        ],
        "tools_needed": ["log_search", "cloudwatch_query"],
    },
    {
        "id": "rb-007",
        "title": "DynamoDB Throttling",
        "symptoms": "dynamodb throttle read write capacity exceeded provisioned throughput hot partition",
        "steps": [
            "Check ThrottledRequests and ConsumedReadCapacityUnits metrics",
            "Identify hot keys/partitions via CloudWatch Contributor Insights",
            "Switch to on-demand capacity or increase provisioned RCU/WCU",
            "Review partition key design for uniform distribution",
        ],
        "tools_needed": ["cloudwatch_query"],
    },
    {
        "id": "rb-008",
        "title": "VPC / Network Connectivity Failure",
        "symptoms": "network connectivity timeout unreachable vpc subnet security group nacl route table dns resolution",
        "steps": [
            "Verify security group inbound/outbound rules",
            "Check Network ACL rules (stateless — both directions)",
            "Confirm route table has correct routes (IGW, NAT, VPC peering)",
            "Use VPC Reachability Analyzer for path diagnosis",
        ],
        "tools_needed": ["describe_network"],
    },
    {
        "id": "rb-009",
        "title": "CloudFront Cache Miss / Origin Error",
        "symptoms": "cloudfront cdn cache miss origin error latency high distribution edge location",
        "steps": [
            "Check CloudFront cache hit ratio and error rate metrics",
            "Review cache behavior settings and TTL configuration",
            "Verify origin is healthy and responding within timeout",
            "Invalidate cache if serving stale/incorrect content",
        ],
        "tools_needed": ["cloudwatch_query"],
    },
    {
        "id": "rb-010",
        "title": "IAM / STS Credential Failure",
        "symptoms": "iam sts assume role credential expired token invalid access key unauthorized security",
        "steps": [
            "Check CloudTrail for AccessDenied or InvalidClientTokenId events",
            "Verify IAM role trust policy allows the calling principal",
            "Check STS session duration limits",
            "Rotate access keys if compromised",
        ],
        "tools_needed": ["get_iam_policy", "log_search"],
    },
]


@dataclass
class TFIDFIndex:
    """Lightweight TF-IDF index over runbook symptom text for retrieval."""

    docs: list[dict] = field(default_factory=list)
    vocab: dict[str, int] = field(default_factory=dict)
    idf: dict[str, float] = field(default_factory=dict)
    tf_matrix: list[dict[str, float]] = field(default_factory=list)

    def build(self, runbooks: list[dict]) -> None:
        self.docs = runbooks
        all_tokens: list[list[str]] = []
        for rb in runbooks:
            text = f"{rb['title']} {rb['symptoms']}"
            tokens = _tokenize(text)
            all_tokens.append(tokens)

        # Build vocab
        doc_count: dict[str, int] = {}
        for tokens in all_tokens:
            for t in set(tokens):
                doc_count[t] = doc_count.get(t, 0) + 1
        n = len(runbooks)
        self.idf = {t: math.log((n + 1) / (df + 1)) + 1 for t, df in doc_count.items()}

        # Build TF vectors
        self.tf_matrix = []
        for tokens in all_tokens:
            tf: dict[str, float] = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
            # Normalize
            max_tf = max(tf.values()) if tf else 1
            tf = {t: v / max_tf for t, v in tf.items()}
            self.tf_matrix.append(tf)

    def query(self, text: str, top_k: int = 3) -> list[dict]:
        tokens = _tokenize(text)
        q_tf: dict[str, float] = {}
        for t in tokens:
            q_tf[t] = q_tf.get(t, 0) + 1
        max_q = max(q_tf.values()) if q_tf else 1
        q_tf = {t: v / max_q for t, v in q_tf.items()}

        scores: list[tuple[float, int]] = []
        for i, doc_tf in enumerate(self.tf_matrix):
            score = 0.0
            for t, qtf in q_tf.items():
                if t in doc_tf and t in self.idf:
                    score += qtf * self.idf[t] * doc_tf[t] * self.idf[t]
            scores.append((score, i))

        scores.sort(key=lambda x: -x[0])
        results = []
        for score, idx in scores[:top_k]:
            if score > 0:
                rb = self.docs[idx].copy()
                rb["relevance_score"] = round(score, 4)
                results.append(rb)
        return results


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


# Singleton index
_index = TFIDFIndex()
_index.build(RUNBOOKS)


def retrieve_runbooks(incident_description: str, top_k: int = 3) -> list[dict]:
    """Retrieve the most relevant runbooks for an incident description."""
    return _index.query(incident_description, top_k=top_k)
