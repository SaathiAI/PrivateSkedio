"""
SkedioAI Agent Envelope
=====================
The outer wrapper that every agent uses to report back to the supervisor.

Each agent wraps its own existing Pydantic models inside this envelope.
No duplicated schemas — agents import their own models from their own files.

Status values:
  - status should mirror the worker's own native status
  - examples:
      Intake   → pending | approved | rejected
      Planner  → pending | approved | rejected | escalate
  - the envelope should not invent a second routing-only status language

Architecture:
  ┌─────────────────────────────────────────────────────┐
  │  AgentOutputEnvelope (same for every agent)         │
  │  { id, agent_name, status, message, data, ... }     │
  │                                                     │
  │  ┌───────────────────────────────────────────────┐  │
  │  │  data: { ... agent's own existing models ... }│  │
  │  │  Intake → IntakeResponse from intake_agent  │  │
  │  │  Planner → PlannerState fields from planner_agent            │  │
  │  │  Chat → response text + tool info             │  │
  │  └───────────────────────────────────────────────┘  │
  └─────────────────────────────────────────────────────┘
"""

from typing import Optional, Dict, Any, Literal
from datetime import datetime
import uuid

from pydantic import BaseModel, Field


class AgentOutputEnvelope(BaseModel):
    """Standard envelope wrapping every agent's output.

    The envelope is the shipping container — always the same shape.
    The `data` field is the actual product — whatever the agent already produces.

    Usage per agent:
      - Intake:     data = {intake_complete, user_profile, canonical_items, ...}
      - Planner:    data = {committed, has_verified_plan, planner_status, ...}
      - Chat:       data = {response_text, tools_used, ...}
    """

    id: str = Field(
        description="Unique envelope ID, e.g. 'env_intake_20260518_143000_abc123'"
    )
    agent_name: Literal["intake", "planner", "chat", "rescheduler", "supervisor"]
    status: str = Field(
        description=(
            "Worker-native status. Do not invent a second envelope-only status layer. "
            "Examples: Intake uses pending/approved/rejected; Planner may use "
            "pending/approved/rejected/escalate."
        )
    )
    message: str = Field(description="User-facing summary text")
    data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Agent's own existing model output — no schema duplication here",
    )
    error: Optional[str] = Field(
        default=None, description="Internal error detail, never shown to user directly"
    )
    created_at: str = Field(description="ISO 8601 timestamp")


# ==============================================================================
# HELPERS
# ==============================================================================


def create_envelope_id(agent_name: str) -> str:
    """Generate a unique envelope ID.

    Format: env_{agent_name}_{YYYYMMDD}_{HHMMSS}_{random_hex}
    """
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    random_hex = uuid.uuid4().hex[:6]
    return f"env_{agent_name}_{timestamp}_{random_hex}"


def make_envelope(
    agent_name: str,
    status: str,
    message: str,
    data: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
) -> dict:
    """Build and return a serialized AgentOutputEnvelope in one call.

    Usage:
        return {"worker_envelope": make_envelope("planner", "rejected", msg, error="timeout")}
    """
    return AgentOutputEnvelope(
        id=create_envelope_id(agent_name),
        agent_name=agent_name,
        status=status,
        message=message,
        data=data,
        error=error,
        created_at=datetime.now().isoformat(),
    ).model_dump()


def summarize_envelope_for_eval(env: dict) -> str:
    """Compact summary of an envelope for the supervisor's _evaluate_turn_with_llm.

    The evaluator needs status + data keys to decide correctly — not just the message.
    Example: status=pending or approved plus data keys tell the supervisor what happened.
    """
    return (
        f"Agent: {env.get('agent_name')}\n"
        f"Status: {env.get('status')}\n"
        f"Message: {env.get('message', '')[:300]}\n"
        f"Data keys: {list((env.get('data') or {}).keys())}\n"
        f"Error: {env.get('error')}"
    ).strip()
