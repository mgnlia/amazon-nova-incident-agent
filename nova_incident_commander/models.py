"""Pydantic models for alerts, steps, and incident reports."""
from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, field_validator


class AlertSeverity(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class AlertSource(str, Enum):
    CLOUDWATCH = "cloudwatch"
    PAGERDUTY = "pagerduty"
    MANUAL = "manual"


class Alert(BaseModel):
    alert_id: str = Field(..., min_length=1, max_length=64)
    title: str = Field(..., min_length=1, max_length=256)
    description: str = Field(..., min_length=1, max_length=2000)
    severity: AlertSeverity
    source: AlertSource = AlertSource.CLOUDWATCH
    resource_id: str = Field(..., min_length=1, max_length=128)
    metric_name: str | None = Field(None, max_length=128)
    metric_value: float | None = None
    region: str = Field(default="us-east-1", max_length=32)

    @field_validator("title", "description")
    @classmethod
    def no_script_tags(cls, v: str) -> str:
        """Basic XSS prevention."""
        forbidden = ["<script", "</script", "javascript:", "onerror=", "onload="]
        v_lower = v.lower()
        for f in forbidden:
            if f in v_lower:
                raise ValueError(f"Invalid content detected: {f}")
        return v


class AgentStep(BaseModel):
    step: int
    kind: str  # "reasoning" | "tool_call" | "tool_result" | "final"
    content: str
    tool_name: str | None = None
    tool_input: dict[str, Any] | None = None
    tool_result: dict[str, Any] | None = None


class ResolutionStatus(str, Enum):
    RESOLVED = "resolved"
    MITIGATED = "mitigated"
    ESCALATED = "escalated"
    FAILED = "failed"


class IncidentReport(BaseModel):
    incident_id: str
    alert: Alert
    severity: AlertSeverity
    summary: str
    root_cause: str
    actions_taken: list[str]
    resolution_status: ResolutionStatus
    follow_up: str
    steps: list[AgentStep]
    runbooks_used: list[str]
    total_steps: int
    duration_seconds: float
    bedrock_model: str


class RunIncidentRequest(BaseModel):
    alert: Alert
    max_steps: int = Field(default=10, ge=1, le=20)
    mode: str = Field(default="mock", pattern="^(mock|bedrock)$")
