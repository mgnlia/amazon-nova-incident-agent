"""
FastAPI application for the Amazon Nova Incident Commander.
Provides REST API for incident submission and agent interaction.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent.core import AgentSession, run_agent, run_agent_mock

app = FastAPI(
    title="Amazon Nova Incident Commander",
    description="AI-powered DevOps incident response agent using Amazon Nova on Bedrock",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session store (swap for DynamoDB in production)
sessions: dict[str, dict] = {}


class IncidentRequest(BaseModel):
    description: str = Field(..., min_length=10, max_length=5000, description="Incident description")
    severity: str = Field(default="high", description="Incident severity: low, medium, high, critical")
    service: str = Field(default="", description="Affected AWS service or application name")
    use_mock: bool = Field(default=False, description="Use mock mode (no AWS credentials needed)")


class IncidentResponse(BaseModel):
    session_id: str
    status: str
    turns_used: int
    model_id: str
    diagnosis: str
    remediation: list[str]
    created_at: str


class HealthResponse(BaseModel):
    status: str
    version: str
    model: str


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(
        status="healthy",
        version="0.2.0",
        model=os.environ.get("BEDROCK_MODEL_ID", "amazon.nova-pro-v1:0"),
    )


@app.post("/incidents", response_model=IncidentResponse)
def create_incident(req: IncidentRequest):
    """Submit an incident for AI-powered diagnosis and remediation."""
    # Determine if we should use mock mode
    use_mock = req.use_mock or os.environ.get("MOCK_MODE", "false").lower() == "true"

    enriched = f"Severity: {req.severity}\n"
    if req.service:
        enriched += f"Service: {req.service}\n"
    enriched += f"\n{req.description}"

    try:
        if use_mock:
            session = run_agent_mock(enriched)
        else:
            session = run_agent(enriched)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")

    # Store session
    result = {
        "session_id": session.session_id,
        "status": session.status,
        "turns_used": session.turns_used,
        "model_id": session.model_id,
        "diagnosis": session.diagnosis,
        "remediation": session.remediation,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    sessions[session.session_id] = result

    return IncidentResponse(**result)


@app.get("/incidents/{session_id}", response_model=IncidentResponse)
def get_incident(session_id: str):
    """Retrieve a previous incident analysis by session ID."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return IncidentResponse(**sessions[session_id])


@app.get("/incidents", response_model=list[IncidentResponse])
def list_incidents():
    """List all incident analyses."""
    return [IncidentResponse(**s) for s in sessions.values()]


@app.post("/demo")
def run_demo():
    """Run a demo incident analysis using mock mode."""
    demo_incident = (
        "Our production API is returning 5xx errors at a rate of ~200/min. "
        "The ALB target group shows 2 out of 5 targets as unhealthy. "
        "Users are reporting intermittent timeouts on the checkout endpoint. "
        "This started approximately 30 minutes ago after a deployment."
    )
    session = run_agent_mock(demo_incident)
    result = {
        "session_id": session.session_id,
        "status": session.status,
        "turns_used": session.turns_used,
        "model_id": session.model_id,
        "diagnosis": session.diagnosis,
        "remediation": session.remediation,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    sessions[session.session_id] = result
    return IncidentResponse(**result)
