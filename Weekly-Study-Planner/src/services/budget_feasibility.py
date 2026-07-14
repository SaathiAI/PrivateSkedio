"""Deterministic budget feasibility for the final intake contract.

This service answers one question:
Can the requested work fit inside the student's realistic available hours?
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from src.models.intake import IntakeAgentOutput, StrictModel


DEFAULT_BUFFER_RATIO = 0.8

BudgetFeasibilityStatus = Literal["feasible", "infeasible", "needs_more_info"]


class BudgetFeasibilityResult(StrictModel):
    status: BudgetFeasibilityStatus
    feasible: bool
    required_hours: float = Field(ge=0)
    available_hours: float = Field(ge=0)
    usable_hours: float = Field(ge=0)
    margin_hours: float

    @model_validator(mode="after")
    def status_matches_feasible_flag(self) -> "BudgetFeasibilityResult":
        if self.status == "feasible" and not self.feasible:
            raise ValueError("feasible status requires feasible=True")
        if self.status != "feasible" and self.feasible:
            raise ValueError("non-feasible status requires feasible=False")
        return self


def _round_hours(value: float) -> float:
    return round(float(value), 2)


def check_budget_feasibility(
    intake_output: IntakeAgentOutput | dict,
    buffer_ratio: float = DEFAULT_BUFFER_RATIO,
) -> BudgetFeasibilityResult:
    """Return fit verdict plus the core budget math."""

    intake = (
        intake_output
        if isinstance(intake_output, IntakeAgentOutput)
        else IntakeAgentOutput.model_validate(intake_output)
    )

    required_hours = sum(
        float(item.estimated_hours)
        for item in intake.study_items
    )
    daily_hours = (
        intake.availability.daily_study_hours
        if intake.availability
        else {}
    )
    available_hours = sum(float(hours) for hours in daily_hours.values())
    usable_hours = available_hours * buffer_ratio
    margin_hours = usable_hours - required_hours

    if not intake.study_items or not daily_hours:
        status: BudgetFeasibilityStatus = "needs_more_info"
        feasible = False
    elif margin_hours >= 0:
        status = "feasible"
        feasible = True
    else:
        status = "infeasible"
        feasible = False

    return BudgetFeasibilityResult(
        status=status,
        feasible=feasible,
        required_hours=_round_hours(required_hours),
        available_hours=_round_hours(available_hours),
        usable_hours=_round_hours(usable_hours),
        margin_hours=_round_hours(margin_hours),
    )


def budget_feasibility_tool(
    intake_output: IntakeAgentOutput | dict,
    buffer_ratio: float = DEFAULT_BUFFER_RATIO,
) -> dict:
    """Tool entrypoint for orchestrators and agents."""

    return check_budget_feasibility(
        intake_output=intake_output,
        buffer_ratio=buffer_ratio,
    ).model_dump()


__all__ = [
    "BudgetFeasibilityResult",
    "DEFAULT_BUFFER_RATIO",
    "budget_feasibility_tool",
    "check_budget_feasibility",
]
