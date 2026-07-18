"""Build and render the deterministic context given to the Planner LLM.

This file converts supervisor/intake state into the exact contract the Planner
model is allowed to see and optimize inside.

Mental model:
- Intake produces the locked contract
- this service reshapes that contract into planner-facing JSON
- Planner should schedule inside this context, not reinterpret the raw intake
  conversation or re-solve calendar math on its own
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from langchain_core.messages import BaseMessage, SystemMessage, ToolMessage

from src.models.intake import IntakeAgentOutput


def planner_request_from_state(state: Any) -> Optional[Any]:
    """Return the PlannerRequest carried by the active Planner state."""

    request = getattr(state, "request", None)
    if request is not None:
        return request

    return None


def planner_intake_from_state(state: Any) -> IntakeAgentOutput:
    """Return the locked Intake contract from the Planner state/request."""

    request = planner_request_from_state(state)
    if request is not None:
        return request.intake
    raise ValueError("Planner state is missing request.intake")


def planner_work_item_targets(state: Any) -> Dict[str, float]:
    """Return target hours from Intake study_items."""

    intake = planner_intake_from_state(state)
    return {
        item.scope_reference_key or item.chapter: round(float(item.estimated_hours), 2)
        for item in intake.study_items
    }


def planner_daily_study_hours(state: Any) -> Dict[str, float]:
    """Return normalized date-keyed hours confirmed by the student."""

    scheduling_context = planner_scheduling_context(state)
    if scheduling_context.get("daily_study_hours"):
        return {
            date: round(float(hours), 2)
            for date, hours in scheduling_context["daily_study_hours"].items()
        }

    intake = planner_intake_from_state(state)
    if intake.availability:
        return {
            date: round(float(hours), 2)
            for date, hours in intake.availability.daily_study_hours.items()
        }
    return {}


def planner_scheduling_context(state: Any) -> Dict[str, Any]:
    """Return the canonical runtime scheduling context for Planner."""

    request = planner_request_from_state(state)
    if request is not None and isinstance(request.scheduling_context, dict):
        return request.scheduling_context

    return {}


def planner_remaining_subtopics_from_state(state: Any) -> List[str]:
    """Return unique backlog subtopics requested by Intake work items."""

    keys = []
    intake = planner_intake_from_state(state)
    for work_item in intake.study_items:
        for key in work_item.remaining_subtopics:
            if key not in keys:
                keys.append(key)
    return keys


def planner_goal_summary(state: Any) -> Dict[str, Any]:
    """Return the Intake goal as a plain dictionary."""

    intake = planner_intake_from_state(state)
    return intake.goal.model_dump() if intake.goal else {}


def planner_subjects(state: Any) -> List[str]:
    """Return unique subjects from the Intake goal or work items."""

    intake = planner_intake_from_state(state)
    if intake.goal and intake.goal.subjects:
        return list(intake.goal.subjects)
    subjects = []
    for item in intake.study_items:
        if item.subject not in subjects:
            subjects.append(item.subject)
    return subjects


def planner_chapters(state: Any) -> List[str]:
    """Return unique chapter names from Intake work items."""

    chapters = []
    intake = planner_intake_from_state(state)
    for item in intake.study_items:
        if item.chapter not in chapters:
            chapters.append(item.chapter)
    return chapters


def planner_start_date(state: Any) -> Optional[str]:
    """Return the goal start date when one exists."""

    intake = planner_intake_from_state(state)
    return intake.goal.start_date if intake.goal else None


def planner_end_date(state: Any) -> Optional[str]:
    """Return the goal end date when one exists."""

    intake = planner_intake_from_state(state)
    return intake.goal.end_date if intake.goal else None


def build_intake_snapshot_for_commit(state: Any) -> Dict[str, Any]:
    """Build the Intake snapshot persisted with a committed plan.

    This snapshot is the audit trail for "what contract produced this plan?"
    It is useful for debugging, rescheduling, and later plan reconstruction.
    """

    request = planner_request_from_state(state)
    intake = planner_intake_from_state(state)
    snapshot = intake.model_dump()

    if request is not None:
        snapshot["planner_request"] = (
            request.model_dump()
            if hasattr(request, "model_dump")
            else {
                "user_id": getattr(request, "user_id", None),
                "intake": intake.model_dump(),
                "scheduling_context": getattr(request, "scheduling_context", None),
            }
        )

    scheduling_context = planner_scheduling_context(state)
    if scheduling_context:
        snapshot["scheduling_context"] = scheduling_context

    return snapshot


def reschedule_budget_targets_from_messages(messages: List[BaseMessage]) -> Dict[str, float]:
    """Return remaining chapter-hour targets from get_active_plan tool output."""

    def progress_budget_from_plan_details(plan_details: Dict[str, Any]) -> Dict[str, Any]:
        """Extract work-item budget data from known active-plan shapes."""

        progress = plan_details.get("progress") or {}
        return (
            progress.get("work_item_budget")
            or plan_details.get("work_item_budget")
            or {}
        )

    for msg in reversed(messages or []):
        if isinstance(msg, SystemMessage) and str(getattr(msg, "content", "")).startswith("[RESCHEDULE PREFETCH CONTEXT]"):
            try:
                content = msg.content.split("[RESCHEDULE PREFETCH CONTEXT]", 1)[1]
                content = content.split("[READ TOOL POLICY]", 1)[0].strip()
                data = json.loads(content)
            except Exception:
                data = {}

            plan_details = ((data.get("active_plan") or {}).get("plan_details") or {})
            work_item_budget = progress_budget_from_plan_details(plan_details)
            remaining_targets = {}
            for chapter, budget in work_item_budget.items():
                if not isinstance(budget, dict):
                    continue
                try:
                    remaining = float(budget.get("remaining", 0) or 0)
                except (TypeError, ValueError):
                    continue
                if remaining > 0:
                    remaining_targets[chapter] = remaining
            if remaining_targets:
                return remaining_targets

        if not isinstance(msg, ToolMessage) or msg.name != "get_active_plan":
            continue
        try:
            data = json.loads(msg.content)
        except Exception:
            continue

        plan_details = data.get("plan_details") or {}
        work_item_budget = progress_budget_from_plan_details(plan_details)
        remaining_targets = {}
        for chapter, budget in work_item_budget.items():
            if not isinstance(budget, dict):
                continue
            try:
                remaining_hours = round(float(budget.get("remaining")), 2)
            except (TypeError, ValueError):
                continue
            if remaining_hours > 0:
                remaining_targets[str(chapter)] = remaining_hours

        if remaining_targets:
            return remaining_targets

    return {}


def build_planner_context(state: Any) -> Dict[str, Any]:
    """Build the locked planner contract JSON shown to the Planner LLM.

    This is the most important planner-facing boundary object in the stack.
    It combines:
    - goal
    - confirmed availability
    - legal available windows
    - normalized study items and hour targets
    """

    intake: IntakeAgentOutput = planner_intake_from_state(state)
    scheduling_context = planner_scheduling_context(state)
    daily_study_hours = planner_daily_study_hours(state)
    timezone_name = (
        scheduling_context.get("timezone")
        or (intake.availability.timezone if intake.availability else "local")
    )
    available_time_windows = scheduling_context.get("available_time_windows") or {}
    calendar_blocks = scheduling_context.get("calendar_blocks") or []

    clean_commitments = scheduling_context.get("time_blocks") or {}
    if not clean_commitments and intake.availability:
        for date_str, commitments in intake.availability.time_blocks.items():
            clean_commitments[date_str] = [
                {
                    "title": commitment.title,
                    "start": commitment.start,
                    "end": commitment.end,
                    "source": commitment.source,
                }
                for commitment in commitments
            ]

    clean_study_items = []
    for work_item in intake.study_items:
        target_minutes = int(round(float(work_item.estimated_hours) * 60))
        clean_study_items.append(
            {
                "scope_reference_key": work_item.scope_reference_key,
                "subject": work_item.subject,
                "chapter": work_item.chapter,
                "estimated_hours": round(float(work_item.estimated_hours), 2),
                "target_minutes": target_minutes,
                "reason": work_item.reason,
                "intake_guidance": work_item.intake_guidance,
                "remaining_subtopics": list(work_item.remaining_subtopics or []),
            }
        )

    return {
        "goal": planner_goal_summary(state),
        "availability": {
            "timezone": timezone_name,
            "daily_study_hours": daily_study_hours,
            "time_blocks": clean_commitments,
            "available_time_windows": available_time_windows,
            "calendar_blocks": calendar_blocks,
        },
        "study_items": clean_study_items,
    }


def render_planner_human_message(state: Any, planner_context: Dict[str, Any]) -> str:
    """Render the compact message that actually hands the contract to the model."""

    compact_contract = json.dumps(planner_context, separators=(",", ":"), default=str)
    return (
        "Locked planner contract JSON:\n"
        f"{compact_contract}\n"
        "Return PlannerOutput only."
    )


# ── Computed fields fill ──────────────────────────────────────────────────────

def _compute_estimated_hours(start_time: str, end_time: str) -> float:
    """Compute session duration in hours from HH:MM start/end times."""
    try:
        start_h, start_m = map(int, start_time.split(":"))
        end_h, end_m = map(int, end_time.split(":"))
        start_minutes = start_h * 60 + start_m
        end_minutes = end_h * 60 + end_m
        if end_minutes > start_minutes:
            return round((end_minutes - start_minutes) / 60, 2)
    except Exception:
        pass
    return 0.0


def fill_computed_fields(plan: Any, planner_context: Dict[str, Any]) -> Any:
    """Fill all computed fields that the LLM should NOT output.
    
    This function mutates the plan in-place and returns it.

    Purpose:
    - keep the LLM output schema smaller
    - compute mechanical fields deterministically in code
    - make verification/commit operate on normalized plan objects
    Fields filled:
    - session.estimated_hours (from start_time/end_time)
    - session.session_id (sequential)
    - day.day_num (1-indexed)
    - day.total_hours (sum of session estimated_hours)
    - day.capacity_hours (from intake daily_study_hours)
    - plan.plan_id (generated)
    - plan.total_hours (sum of day total_hours)
    
    Args:
        plan: StudyPlan object or dict with days/sessions
        planner_context: The locked planner context dict (has availability.daily_study_hours)
    
    Returns:
        The same plan object with all computed fields filled.
    """
    from src.models.planner import StudyPlan, StudyDay, StudySession

    # Accept dict or Pydantic model
    if isinstance(plan, dict):
        plan = StudyPlan.model_validate(plan)
    
    # Get daily_study_hours from context
    availability = planner_context.get("availability") or {}
    confirmed_hours = availability.get("daily_study_hours") or {}
    
    # Generate plan_id
    if not plan.plan_id:
        from datetime import datetime
        import uuid
        now = datetime.now()
        plan.plan_id = f"plan_{now.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    
    # Fill plan.total_hours
    # Process each day
    plan_total = 0.0
    
    for day_idx, day in enumerate(plan.days):
        # Always code-owned
        day.day_num = day_idx + 1
    
        # Always code-owned
        day.capacity_hours = (
            round(float(confirmed_hours[day.date]), 2)
            if day.date in confirmed_hours
            else None
        )
    
        day_total = 0.0
    
        for session_idx, session in enumerate(day.sessions):
            # Always code-owned
            session.session_id = f"sess_{day_idx + 1:02d}_{session_idx + 1:02d}"
    
            # Always code-owned
            session.estimated_hours = _compute_estimated_hours(
                session.start_time,
                session.end_time,
            )
    
            # DO NOT auto-fill allocated_hours here.
            # allocated_hours is LLM-owned planning/accounting.
            # If it is missing or wrong, verifier should fail and trigger repair.
    
            day_total += session.estimated_hours or 0.0
    
        # Always code-owned
        day.total_hours = round(day_total, 2)
        plan_total += day_total
    
    # Always code-owned
    plan.total_hours = round(plan_total, 2)
    
    return plan
