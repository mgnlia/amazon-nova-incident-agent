"""
Amazon Nova Incident Commander — FastAPI Application
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

# Adjust import path when running with `uvicorn api.main:app` from project root
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.core import IncidentCommander

app = FastAPI(
    title="Amazon Nova Incident Commander",
    description="AI-powered DevOps incident response agent powered by Amazon Nova Lite on Bedrock.",
    version="0.1.0",
)

_commander = IncidentCommander()
_static_dir = Path(__file__).resolve().parent.parent / "static"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the single-page UI."""
    html_file = _static_dir / "index.html"
    if not html_file.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    return HTMLResponse(content=html_file.read_text(encoding="utf-8"))


@app.get("/health")
async def health():
    """Health-check endpoint."""
    return {"status": "ok"}


class AlertPayload(BaseModel):
    alert_type: str
    service: str
    severity: str
    message: str

    model_config = {"extra": "allow"}


@app.post("/incident")
async def create_incident(payload: AlertPayload):
    """
    Ingest an alert, run the Nova reasoning pipeline, and return an IncidentReport.
    """
    try:
        raw = payload.model_dump()
        report = _commander.handle(raw)
        return JSONResponse(content=report.to_dict())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}")
