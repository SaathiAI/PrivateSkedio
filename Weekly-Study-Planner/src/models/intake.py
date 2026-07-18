"""Pydantic models for the SkedioAI intake contract.

These models define the data shape that Intake validates and hands to Planner.
"""

from __future__ import annotations

from typing import Annotated, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


IntakeStatus = Literal["approved", "pending", "rejected"]

StudyHour = Annotated[float, Field(ge=0)]


class StrictModel(BaseModel):
    """Base model that rejects accidental schema drift."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ScopeItem(StrictModel):
    subject: str = Field(
        min_length=1,
        description="Subject name, e.g. Mathematics or Science.",
    )
    chapter: str = Field(
        min_length=1,
        description="Chapter name.",
    )
    intent: Optional[str] = Field(
        default=None,
        description="Optional purpose for this scope item.",
    )


class Goal(StrictModel):
    """High-level planning target for the current short planning window."""

    title: Optional[str] = Field(
        default=None,
        description="Short title for the intake goal.",
    )
    subjects: List[str] = Field(
        default_factory=list,
        description="Subjects included in the goal.",
    )
    start_date: Optional[str] = Field(
        default=None,
        description="Plan start date in YYYY-MM-DD format.",
    )
    end_date: Optional[str] = Field(
        default=None,
        description="Plan end date in YYYY-MM-DD format.",
    )
    deadline_datetime: Optional[str] = Field(
        default=None,
        description="Plan cutoff datetime in ISO format.",
    )
    study_scope: List[ScopeItem] = Field(
        default_factory=list,
        description="Academic scope included in this intake.",
    )


class Commitment(StrictModel):
    """One hard no-study block or protected rest window on a specific date."""

    title: str = Field(
        min_length=1,
        description="Short label for the blocker or rest window.",
    )
    start: Optional[str] = Field(
        default=None,
        description="Local start time in HH:MM format when known.",
    )
    end: Optional[str] = Field(
        default=None,
        description="Local end time in HH:MM format when known.",
    )
    source: Literal["user_commitment", "user_rest_window"] = Field(
        description="Commitment source type."
    )


class Availability(StrictModel):
    """Student-confirmed planning constraints, not raw inferred free time.

    `daily_study_hours` is the student's realistic focused capacity.
    `time_blocks` are hard blockers/rest windows the planner must respect.
    """

    timezone: Optional[str] = Field(
        default=None,
        description="Student's local timezone in IANA format, e.g. Asia/Kolkata.",
    )
    daily_study_hours: Dict[str, StudyHour] = Field(
        default_factory=dict,
        description="Date-keyed focused study hours.",
    )
    time_blocks: Dict[str, List[Commitment]] = Field(
        default_factory=dict,
        description="Date-keyed commitments and rest windows.",
    )
    planning_notes: List[str] = Field(
        default_factory=list,
        description="General planner-facing notes.",
    )
    @model_validator(mode="before")
    @classmethod
    def repair_common_llm_nulls(cls, data):
        if not isinstance(data, dict):
            return data

        data = dict(data)

        if data.get("daily_study_hours") is None:
            data["daily_study_hours"] = {}

        if data.get("time_blocks") is None:
            data["time_blocks"] = {}

        if data.get("planning_notes") is None:
            data["planning_notes"] = []

        return data


class WorkItem(StrictModel):
    """One planner-visible chunk of study work derived from scope/backlog truth."""

    scope_reference_key: Optional[str] = Field(
        default=None,
        description="Backlog match key for this work item.",
    )
    subject: str = Field(
        min_length=1,
        description="Subject for this planner-visible work item.",
    )
    chapter: str = Field(
        min_length=1,
        description="Chapter name.",
    )
    estimated_hours: float = Field(
        gt=0,
        description="Estimated focused study hours required.",
    )
    reason: Optional[str] = Field(
        default=None,
        description="Short reason this work is included or prioritized.",
    )
    planning_notes: List[str] = Field(
        default_factory=list,
        description="Planner-facing notes for this work item.",
    )
    remaining_subtopics: List[str] = Field(
        default_factory=list,
        description=(
            "Only exact backlog/content handles, such as match_key values returned "
            "by query_backlog. Empty when none exist."
        ),
    )


class IntakeAgentOutput(StrictModel):
    """Finalized LLM-facing intake output.

    This is the object that crosses from Intake into validation and then into
    planner handoff if approved.
    """

    status: IntakeStatus = Field(
        description="Intake lifecycle status."
    )
    message: str = Field(
        description="Student-facing reply for this intake turn."
    )
    goal: Optional[Goal] = Field(
        default=None,
        description="Current intake goal.",
    )
    availability: Optional[Availability] = Field(
        default=None,
        description="Student capacity and constraints for the contract window.",
    )
    study_items: List[WorkItem] = Field(
        default_factory=list,
        description="Planner-visible work items.",
    )

    @model_validator(mode="before")
    @classmethod
    def repair_common_llm_nulls(cls, data):
        if not isinstance(data, dict):
            return data
    
        data = dict(data)
    
        if data.get("study_items") is None:
            data["study_items"] = []
    
        return data


__all__ = [
    "Availability",
    "Commitment",
    "Goal",
    "IntakeAgentOutput",
    "IntakeStatus",
    "ScopeItem",
    "StrictModel",
    "WorkItem",
]
