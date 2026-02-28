"""
Amazon Nova Incident Commander — Core Agent Loop
AlertIngester → RunbookStore (RAG) → NovaClient (Bedrock) → IncidentCommander
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field, asdict
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class Alert:
    alert_type: str
    service: str
    severity: str
    message: str


@dataclass
class Runbook:
    id: str
    title: str
    tags: list[str]
    steps: list[str]


@dataclass
class IncidentReport:
    alert: dict
    matched_runbook: str
    runbook_steps: list[str]
    nova_reasoning: str
    remediation_actions: list[str]
    resolved: bool
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# AlertIngester
# ---------------------------------------------------------------------------

class AlertIngester:
    """Validates and normalises incoming alert payloads."""

    REQUIRED_FIELDS = {"alert_type", "service", "severity", "message"}

    def ingest(self, raw: dict) -> Alert:
        missing = self.REQUIRED_FIELDS - raw.keys()
        if missing:
            raise ValueError(f"Alert payload missing fields: {missing}")
        return Alert(
            alert_type=str(raw["alert_type"]),
            service=str(raw["service"]),
            severity=str(raw["severity"]).lower(),
            message=str(raw["message"]),
        )


# ---------------------------------------------------------------------------
# RunbookStore  (in-memory, cosine-similarity retrieval)
# ---------------------------------------------------------------------------

_SAMPLE_RUNBOOKS: list[dict] = [
    {
        "id": "high_cpu",
        "title": "High CPU Utilisation",
        "tags": ["cpu", "performance", "compute", "load", "throttle", "spike"],
        "steps": [
            "1. SSH into the affected host and run `top` / `htop` to identify the offending process.",
            "2. Check recent deployments — roll back if a new release correlates with the spike.",
            "3. Scale out the Auto Scaling Group by +2 instances.",
            "4. Set a CloudWatch alarm to page on-call if CPU > 85 % for 5 minutes.",
            "5. Profile the hot process with `py-spy` or `perf` and file a performance ticket.",
        ],
    },
    {
        "id": "disk_full",
        "title": "Disk / Volume Full",
        "tags": ["disk", "storage", "volume", "space", "inode", "filesystem", "full"],
        "steps": [
            "1. Run `df -h` and `du -sh /*` to locate the largest directories.",
            "2. Clear log files older than 7 days: `find /var/log -mtime +7 -delete`.",
            "3. Remove unused Docker images: `docker system prune -af`.",
            "4. Expand the EBS volume via AWS Console and run `resize2fs /dev/xvda1`.",
            "5. Set up a CloudWatch disk-usage alarm at 80 % threshold.",
        ],
    },
    {
        "id": "service_down",
        "title": "Service / Process Down",
        "tags": ["service", "down", "crash", "unreachable", "timeout", "error", "503", "502"],
        "steps": [
            "1. Check service status: `systemctl status <service>` or inspect ECS/K8s pod logs.",
            "2. Review application logs for the root-cause exception or OOM event.",
            "3. Restart the service: `systemctl restart <service>` or trigger an ECS task replacement.",
            "4. Validate health endpoint responds with HTTP 200.",
            "5. Notify stakeholders via PagerDuty and open a post-mortem ticket.",
        ],
    },
]


def _bag_of_words_vector(text: str, vocab: list[str]) -> np.ndarray:
    """Simple bag-of-words vector for cosine similarity (no external deps)."""
    words = set(text.lower().split())
    return np.array([1.0 if w in words else 0.0 for w in vocab], dtype=np.float32)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


class RunbookStore:
    """In-memory runbook store with cosine-similarity retrieval."""

    def __init__(self) -> None:
        self._runbooks: list[Runbook] = [
            Runbook(**rb) for rb in _SAMPLE_RUNBOOKS
        ]
        # Build shared vocabulary from all tag words
        all_words: set[str] = set()
        for rb in self._runbooks:
            for tag in rb.tags:
                all_words.update(tag.lower().split())
        self._vocab: list[str] = sorted(all_words)
        # Pre-compute runbook vectors
        self._vectors: list[np.ndarray] = [
            _bag_of_words_vector(" ".join(rb.tags), self._vocab)
            for rb in self._runbooks
        ]

    def retrieve(self, alert: Alert, top_k: int = 1) -> list[Runbook]:
        query_text = f"{alert.alert_type} {alert.service} {alert.message}"
        query_vec = _bag_of_words_vector(query_text, self._vocab)
        scores = [
            _cosine_similarity(query_vec, rb_vec)
            for rb_vec in self._vectors
        ]
        ranked = sorted(
            zip(scores, self._runbooks), key=lambda x: x[0], reverse=True
        )
        return [rb for _, rb in ranked[:top_k]]


# ---------------------------------------------------------------------------
# NovaClient  (Amazon Bedrock converse API, mock fallback)
# ---------------------------------------------------------------------------

_MOCK_REASONING = (
    "⚠️  [Mock Mode — Bedrock credentials not configured]\n\n"
    "Based on the alert details, the recommended course of action is:\n"
    "  • Identify the root cause using the matched runbook steps.\n"
    "  • Escalate to the on-call engineer if automated remediation fails.\n"
    "  • Document findings in the post-mortem tracker.\n\n"
    "This reasoning was generated locally because AWS Bedrock credentials "
    "were unavailable or the model returned an error."
)


class NovaClient:
    """Thin wrapper around Amazon Bedrock converse() for Nova Lite."""

    MODEL_ID = "amazon.nova-lite-v1:0"

    def __init__(self) -> None:
        self._client = None

    def _get_client(self):
        if self._client is None:
            import boto3
            self._client = boto3.client("bedrock-runtime", region_name="us-east-1")
        return self._client

    def reason(self, alert: Alert, runbook: Runbook) -> str:
        prompt = (
            f"You are a senior DevOps incident commander.\n\n"
            f"ALERT:\n"
            f"  Type     : {alert.alert_type}\n"
            f"  Service  : {alert.service}\n"
            f"  Severity : {alert.severity}\n"
            f"  Message  : {alert.message}\n\n"
            f"MATCHED RUNBOOK: {runbook.title}\n"
            f"RUNBOOK STEPS:\n"
            + "\n".join(f"  {s}" for s in runbook.steps)
            + "\n\nAnalyse the alert, explain the likely root cause, and confirm "
            "which runbook steps are most critical. Be concise."
        )
        try:
            client = self._get_client()
            response = client.converse(
                modelId=self.MODEL_ID,
                messages=[{"role": "user", "content": [{"text": prompt}]}],
            )
            output = response["output"]["message"]["content"]
            return " ".join(block.get("text", "") for block in output).strip()
        except Exception:
            return _MOCK_REASONING


# ---------------------------------------------------------------------------
# IncidentCommander  (orchestrator)
# ---------------------------------------------------------------------------

class IncidentCommander:
    """Orchestrates the full incident-response pipeline."""

    def __init__(self) -> None:
        self.ingester = AlertIngester()
        self.store = RunbookStore()
        self.nova = NovaClient()

    def _mock_remediate(self, runbook: Runbook, alert: Alert) -> list[str]:
        """Simulate automated remediation actions."""
        actions = [
            f"[AUTO] Triggered runbook '{runbook.title}' for service '{alert.service}'.",
            f"[AUTO] Sent PagerDuty notification — severity: {alert.severity}.",
            f"[AUTO] Created JIRA ticket INC-{abs(hash(alert.message)) % 9000 + 1000}.",
            "[AUTO] Snapshot of current metrics captured to S3.",
        ]
        if alert.severity in ("critical", "high"):
            actions.append("[AUTO] Escalated to VP Engineering via SMS.")
        return actions

    def handle(self, raw_alert: dict) -> IncidentReport:
        alert = self.ingester.ingest(raw_alert)
        runbooks = self.store.retrieve(alert, top_k=1)
        best_runbook = runbooks[0] if runbooks else Runbook(
            id="generic",
            title="Generic Incident Response",
            steps=["1. Investigate logs.", "2. Escalate to on-call.", "3. Open post-mortem."],
            tags=[],
        )
        reasoning = self.nova.reason(alert, best_runbook)
        actions = self._mock_remediate(best_runbook, alert)
        return IncidentReport(
            alert={"alert_type": alert.alert_type, "service": alert.service,
                   "severity": alert.severity, "message": alert.message},
            matched_runbook=best_runbook.title,
            runbook_steps=best_runbook.steps,
            nova_reasoning=reasoning,
            remediation_actions=actions,
            resolved=True,
        )
