"""
Core agentic loop: Amazon Nova on Bedrock with tool-use.
Implements the full converse → toolUse → toolResult → converse cycle.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

import boto3

from agent.tools import TOOL_SPECS, execute_tool

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert AWS DevOps Incident Commander. Your job is to diagnose and resolve cloud infrastructure incidents quickly and accurately.

When given an incident report:
1. First, retrieve relevant runbooks using the retrieve_runbook tool to find standard procedures
2. Then, use the appropriate diagnostic tools (cloudwatch_query, log_search, run_ssm_command, etc.) to gather data
3. Analyze the data and correlate findings across multiple signals
4. Provide a clear diagnosis with root cause
5. Recommend specific remediation steps with commands where applicable

Always explain your reasoning. Be specific about metrics, thresholds, and AWS resource identifiers.
Prioritize by severity: data loss > service outage > performance degradation > cosmetic issues."""

MAX_TURNS = 15
DEFAULT_MODEL = "amazon.nova-pro-v1:0"
FALLBACK_MODEL = "amazon.nova-lite-v1:0"


@dataclass
class ConversationTurn:
    role: str
    content: Any
    tool_calls: list[dict] = field(default_factory=list)
    tool_results: list[dict] = field(default_factory=list)


@dataclass
class AgentSession:
    session_id: str
    model_id: str = DEFAULT_MODEL
    history: list[dict] = field(default_factory=list)
    turns_used: int = 0
    status: str = "active"  # active | completed | error
    diagnosis: str = ""
    remediation: list[str] = field(default_factory=list)


def create_bedrock_client():
    """Create a Bedrock Runtime client."""
    region = os.environ.get("AWS_REGION", "us-east-1")
    return boto3.client("bedrock-runtime", region_name=region)


def run_agent(incident_description: str, session: AgentSession | None = None) -> AgentSession:
    """
    Run the full agentic loop for an incident.
    Loops: user msg → model response → tool calls → tool results → model response → ...
    Stops when model gives final answer (no more tool calls) or MAX_TURNS reached.
    """
    if session is None:
        import uuid
        session = AgentSession(session_id=str(uuid.uuid4()))

    client = create_bedrock_client()

    # Initialize conversation with incident
    if not session.history:
        session.history.append({
            "role": "user",
            "content": [{"text": f"INCIDENT REPORT:\n\n{incident_description}"}],
        })

    while session.turns_used < MAX_TURNS and session.status == "active":
        session.turns_used += 1

        try:
            response = client.converse(
                modelId=session.model_id,
                system=[{"text": SYSTEM_PROMPT}],
                messages=session.history,
                toolConfig={"tools": TOOL_SPECS},
                inferenceConfig={
                    "maxTokens": 4096,
                    "temperature": 0.1,
                    "topP": 0.9,
                },
            )
        except client.exceptions.ThrottlingException:
            logger.warning("Throttled on %s, falling back to %s", session.model_id, FALLBACK_MODEL)
            session.model_id = FALLBACK_MODEL
            continue
        except Exception as e:
            logger.error("Bedrock API error: %s", e)
            session.status = "error"
            session.diagnosis = f"Agent error: {e}"
            break

        output = response.get("output", {})
        message = output.get("message", {})
        stop_reason = response.get("stopReason", "end_turn")

        # Add assistant message to history
        session.history.append(message)

        # Check if model wants to use tools
        if stop_reason == "tool_use":
            tool_results = _process_tool_calls(message)
            if tool_results:
                session.history.append({
                    "role": "user",
                    "content": tool_results,
                })
        else:
            # Model gave final answer — extract it
            session.status = "completed"
            session.diagnosis = _extract_text(message)
            break

    if session.turns_used >= MAX_TURNS and session.status == "active":
        session.status = "completed"
        session.diagnosis += "\n\n[Agent reached maximum turns — partial analysis provided]"

    return session


def _process_tool_calls(message: dict) -> list[dict]:
    """Extract tool_use blocks, execute tools, return toolResult blocks."""
    content = message.get("content", [])
    results = []

    for block in content:
        if "toolUse" in block:
            tool_use = block["toolUse"]
            tool_name = tool_use["name"]
            tool_input = tool_use.get("input", {})
            tool_use_id = tool_use["toolUseId"]

            logger.info("Executing tool: %s with input: %s", tool_name, json.dumps(tool_input)[:200])

            result = execute_tool(tool_name, tool_input)

            results.append({
                "toolResult": {
                    "toolUseId": tool_use_id,
                    "content": [{"json": result}],
                }
            })

    return results


def _extract_text(message: dict) -> str:
    """Extract text content from a message."""
    content = message.get("content", [])
    texts = []
    for block in content:
        if "text" in block:
            texts.append(block["text"])
    return "\n".join(texts)


def run_agent_mock(incident_description: str) -> AgentSession:
    """
    Run a mock agent loop without calling Bedrock.
    Used for demos and testing when AWS credentials aren't available.
    Simulates the full agentic flow with realistic tool calls and diagnosis.
    """
    import uuid
    from agent.runbooks import retrieve_runbooks

    session = AgentSession(session_id=str(uuid.uuid4()), model_id="mock")

    # Step 1: Retrieve runbooks
    runbooks = retrieve_runbooks(incident_description, top_k=2)

    # Step 2: Simulate diagnostic tool calls based on runbook
    tool_calls_made = []
    tool_results_collected = []

    if runbooks:
        top_rb = runbooks[0]
        for tool_name in top_rb.get("tools_needed", [])[:2]:
            # Generate plausible input
            mock_input = _generate_mock_input(tool_name, incident_description)
            result = execute_tool(tool_name, mock_input)
            tool_calls_made.append({"tool": tool_name, "input": mock_input})
            tool_results_collected.append({"tool": tool_name, "result": result})
            session.turns_used += 1

    # Step 3: Generate diagnosis
    session.turns_used += 1
    rb_titles = [rb["title"] for rb in runbooks]
    rb_steps = runbooks[0]["steps"] if runbooks else ["No matching runbook found"]

    session.diagnosis = _generate_mock_diagnosis(
        incident_description, rb_titles, rb_steps, tool_results_collected
    )
    session.remediation = rb_steps if runbooks else ["Investigate manually"]
    session.status = "completed"

    # Build readable history
    session.history = [
        {"role": "user", "content": [{"text": f"INCIDENT REPORT:\n\n{incident_description}"}]},
    ]
    for tc in tool_calls_made:
        session.history.append({
            "role": "assistant",
            "content": [{"text": f"Using tool: {tc['tool']}"}],
        })
    session.history.append({
        "role": "assistant",
        "content": [{"text": session.diagnosis}],
    })

    return session


def _generate_mock_input(tool_name: str, incident: str) -> dict:
    """Generate plausible mock input for a tool based on incident text."""
    incident_lower = incident.lower()
    if tool_name == "cloudwatch_query":
        if "cpu" in incident_lower or "memory" in incident_lower:
            return {"namespace": "AWS/EC2", "metric_name": "CPUUtilization", "period_minutes": 60}
        if "rds" in incident_lower or "database" in incident_lower:
            return {"namespace": "AWS/RDS", "metric_name": "DatabaseConnections", "period_minutes": 60}
        if "lambda" in incident_lower:
            return {"namespace": "AWS/Lambda", "metric_name": "Duration", "period_minutes": 30}
        if "5xx" in incident_lower or "error" in incident_lower:
            return {"namespace": "AWS/ApplicationELB", "metric_name": "HTTPCode_ELB_5XX_Count", "period_minutes": 60}
        return {"namespace": "AWS/EC2", "metric_name": "CPUUtilization", "period_minutes": 60}
    if tool_name == "log_search":
        return {"log_group": "/aws/application/prod", "filter_pattern": "ERROR", "minutes_ago": 30}
    if tool_name == "run_ssm_command":
        return {"instance_id": "i-0abc123def456", "command": "top -bn1 | head -20"}
    if tool_name == "describe_network":
        return {"resource_id": "i-0abc123def456"}
    if tool_name == "get_iam_policy":
        return {"principal": "AppServiceRole"}
    if tool_name == "run_sql_query":
        return {
            "cluster_arn": "arn:aws:rds:us-east-1:123456789012:cluster:prod-db",
            "database": "appdb",
            "sql": "SELECT state, count(*) FROM pg_stat_activity GROUP BY state",
        }
    return {}


def _generate_mock_diagnosis(
    incident: str,
    runbook_titles: list[str],
    steps: list[str],
    tool_results: list[dict],
) -> str:
    """Generate a realistic mock diagnosis."""
    lines = [
        "## Incident Analysis\n",
        f"**Incident:** {incident[:200]}\n",
        "### Matched Runbooks",
    ]
    for title in runbook_titles:
        lines.append(f"- {title}")

    lines.append("\n### Diagnostic Findings\n")
    for tr in tool_results:
        tool = tr["tool"]
        result = tr["result"]
        lines.append(f"**{tool}:**")
        if tool == "cloudwatch_query":
            dps = result.get("datapoints", [])
            if dps:
                vals = [dp["value"] for dp in dps]
                lines.append(f"  - Metric: {result.get('metric_name', 'N/A')}")
                lines.append(f"  - Average: {sum(vals)/len(vals):.1f}, Peak: {max(vals):.1f}")
                lines.append(f"  - ⚠️ Values are elevated — above normal operating threshold")
        elif tool == "log_search":
            events = result.get("events", [])
            lines.append(f"  - Found {len(events)} error events in the last 30 minutes")
            for ev in events[:2]:
                lines.append(f"  - `{ev['message'][:100]}`")
        elif tool == "run_ssm_command":
            lines.append(f"  - Instance: {result.get('instance_id', 'N/A')}")
            stdout = result.get("stdout", "")
            if "cpu" in stdout.lower() or "%Cpu" in stdout:
                lines.append(f"  - ⚠️ High CPU detected in process list")
        else:
            lines.append(f"  - Data collected successfully")

    lines.append("\n### Root Cause Assessment\n")
    lines.append(
        "Based on the diagnostic data collected, the incident correlates with the "
        f"**{runbook_titles[0] if runbook_titles else 'Unknown'}** pattern. "
        "Multiple signals confirm the diagnosis."
    )

    lines.append("\n### Recommended Remediation\n")
    for i, step in enumerate(steps, 1):
        lines.append(f"{i}. {step}")

    lines.append("\n### Severity: **HIGH** — Immediate action recommended")

    return "\n".join(lines)
