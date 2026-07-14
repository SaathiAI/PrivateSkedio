"""Planner Pydantic contracts for SkedioAI.

These models define the planner-facing output shape after intake is locked.

Mental model:
- Intake says what must be studied and under what constraints
- Planner produces a concrete timed plan in this schema
- verifier/commit code can then inspect and persist the result deterministically
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ── Planner boundary objects ──────────────────────────────────────────────────


class PlannerRequest(BaseModel):
    """Boundary object passed from Supervisor/Intake into Planner.

    Planner still adapts the clean intake contract into its internal budget and
    verifier structures, but this is the handoff shape other agents should use.
    """

    user_id: str
    intake: Any  # IntakeAgentOutput — use Any to avoid circular import
    scheduling_context: Optional[Dict[str, Any]] = None
    active_plan_context: Optional[Dict[str, Any]] = None

    @model_validator(mode="after")
    def normalize_intake_contract(self):
        """Accept raw Intake dictionaries at process boundaries."""

        if isinstance(self.intake, dict):
            from src.models.intake import IntakeAgentOutput

            self.intake = IntakeAgentOutput.model_validate(self.intake)
        return self


class PlannerTimingEntry(BaseModel):
    """One node's timing measurement inside the planner graph."""

    stage: str
    duration_seconds: float
    details: Optional[Dict[str, Any]] = None


class PlannerTiming(BaseModel):
    """Accumulated per-node timing for the planner graph run."""

    entries: List[PlannerTimingEntry] = Field(default_factory=list)
    total_stage_seconds: float = 0.0


class PlannerState(BaseModel):
    """Runtime state for the Planner LangGraph.

    Key fields:
    - `request`: immutable handoff from supervisor/intake
    - `unverified_plan`: latest model-produced draft; not trusted yet
    - `verified_plan`: deterministic-verifier-approved draft that is safe to show/commit
    - `planner_status`: what the supervisor should know about this turn
    """

    request: PlannerRequest
    commit_requested: bool = False
    messages: Annotated[List[BaseMessage], add_messages]
    planner_status: Optional[
        Literal[
            "pending",
            "needs_input",
            "awaiting_approval",
            "rejected",
            "committed",
            "escalate",
        ]
    ]
    committed: bool
    user_context: Optional[str]
    has_active_plan: bool = False
    active_plan_id: Optional[str] = None
    auto_mode: bool = False
    has_overflow: bool = False
    clashes: Optional[List[Dict[str, Any]]]
    unverified_plan: Optional[StudyPlan] = None
    verify_attempts: int = 0
    verified_plan: Optional[StudyPlan] = None
    verify_errors: Optional[Dict[str, Any]] = None
    timing: Optional[PlannerTiming] = None


class StudyContent(BaseModel):
    """Checkbox/content item inside a scheduled session."""

    model_config = ConfigDict(extra="forbid")

    name: str
    match_key: Optional[str] = None
    subjects: List[str] = Field(default_factory=list)
    chapters: List[str] = Field(default_factory=list)
    type: Literal[
        "topic",
        "subtopic",
        "exercise",
        "practice",
        "revision",
        "practice_target",
        "revision_target",
        "mock_test",
    ] = "subtopic"


class SessionAllocation(BaseModel):
    """Hours from a session assigned to one Intake work item/chapter."""

    model_config = ConfigDict(extra="forbid")

    subject: str
    chapter: str
    hours: float


class StudySession(BaseModel):
    """A single study session. LLM outputs start_time, end_time, title, contents.
    
    Code fills: session_id, estimated_hours, allocated_hours (from start/end time).
    """

    model_config = ConfigDict(extra="forbid")

    session_id: Optional[str] = None
    title: str
    session_type: Literal[
        "chapter",
        "focused_chapter",
        "mixed",
        "revision",
        "practice",
        "review",
        "mock_test",
    ] = "chapter"
    estimated_hours: Optional[float] = Field(
        default=None,
        description="Computed by code from start_time/end_time. LLM should NOT output this.",
    )
    start_time: str = Field(description="Start time in 24h format, e.g. '16:00'")
    end_time: str = Field(description="End time in 24h format, e.g. '17:30'")
    allocated_hours: List[SessionAllocation] = Field(default_factory=list)
    contents: List[StudyContent] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def infer_estimated_hours_when_missing(cls, data):
        """Auto-compute estimated_hours from start_time/end_time if not provided."""
        if not isinstance(data, dict) or data.get("estimated_hours") is not None:
            return data

        data = dict(data)
        start_time = data.get("start_time")
        end_time = data.get("end_time")
        if start_time and end_time:
            try:
                start_h, start_m = map(int, start_time.split(":"))
                end_h, end_m = map(int, end_time.split(":"))
                start_minutes = start_h * 60 + start_m
                end_minutes = end_h * 60 + end_m
                if end_minutes > start_minutes:
                    data["estimated_hours"] = round(
                        (end_minutes - start_minutes) / 60,
                        2,
                    )
            except Exception:
                pass

        return data


class StudyDay(BaseModel):
    """A single day in the plan. LLM outputs date and sessions.
    
    Code fills: day_num, total_hours, capacity_hours.
    """

    model_config = ConfigDict(extra="forbid")

    day_num: Optional[int] = Field(
        default=None,
        description="Computed by code (1-indexed position in plan). LLM should NOT output this.",
    )
    date: str
    total_hours: Optional[float] = Field(
        default=None,
        description="Computed by code (sum of session estimated_hours). LLM should NOT output this.",
    )
    capacity_hours: Optional[float] = Field(
        default=None,
        description="Computed by code from intake daily_study_hours. LLM should NOT output this.",
    )
    sessions: List[StudySession] = Field(default_factory=list)


class StudyPlan(BaseModel):
    """Concrete timed plan produced by Planner and verified by code.
    
    LLM outputs: days with sessions.
    Code fills: plan_id, total_hours, day_num, total_hours per day, capacity_hours, estimated_hours per session.
    """

    model_config = ConfigDict(extra="forbid")

    plan_id: Optional[str] = Field(
        default=None,
        description="Computed by code. LLM should NOT output this.",
    )
    total_hours: Optional[float] = Field(
        default=None,
        description="Computed by code (sum of all session estimated_hours). LLM should NOT output this.",
    )
    days: List[StudyDay] = Field(default_factory=list)


# Resolve forward references (PlannerState uses StudyPlan)
PlannerState.model_rebuild()


class PlannerOutput(BaseModel):
    """Top-level planner response contract returned by planner workers.

    This is intentionally one level above `StudyPlan` so the model can also say
    "needs_input" or return warnings without pretending a valid plan exists.
    """

    model_config = ConfigDict(extra="forbid")

    status: Literal["needs_input", "draft_ready", "planned", "failed"]
    message: str
    math_scratchpad: str = Field(
        default="",
        description=(
            "Compact audit only, max 600 characters. Include target total, planned total, "
            "daily hours check, work item hours check, and overlap/cutoff check. "
            "Do not write step-by-step reasoning."
        ),
    )
    plan: Optional[StudyPlan] = None
    warnings: List[str] = Field(default_factory=list)
    requires_user_input: bool = False

    @model_validator(mode="after")
    def normalize_status(self):
        if self.status == "planned":
            self.status = "draft_ready"
        return self


__all__ = [
    "PlannerOutput",
    "PlannerRequest",
    "PlannerState",
    "PlannerTiming",
    "PlannerTimingEntry",
    "SessionAllocation",
    "StudyContent",
    "StudyDay",
    "StudyPlan",
    "StudySession",
]
