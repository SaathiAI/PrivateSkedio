"""Build and read the rescheduler runtime context.

This file wraps the normal planner context with extra authority rules for
rescheduling.

Mental model:
- Intake owns contract-level facts such as scope, deadlines, and confirmed hours
- rescheduler owns rearranging unfinished future work inside that locked contract

Ownership:
- describe what part of planner truth is locked
- describe what the rescheduler is allowed to change
- render compact runtime guidance for the worker
- separate locked contract truth from live active-plan truth
"""

from __future__ import annotations

import json
from typing import Any, Dict

from src.services.planner_context import (
    build_planner_context,
)


def _active_plan_context_from_state(state: Any) -> Dict[str, Any]:
    """Return the active plan snapshot carried by the Planner request."""

    request = getattr(state, "request", None)
    active_plan_context = getattr(request, "active_plan_context", None) if request else None
    if isinstance(active_plan_context, dict):
        return active_plan_context
    return {"has_plan": False, "plan_details": None}


def _work_item_progress_from_active_plan(active_plan_context: Dict[str, Any]) -> Dict[str, Any]:
    """Return live work-item progress from the active plan snapshot."""

    plan_details = active_plan_context.get("plan_details") or {}
    progress = plan_details.get("progress") or {}
    work_item_budget = progress.get("work_item_budget") or {}
    return work_item_budget if isinstance(work_item_budget, dict) else {}


def build_reschedule_plan_context(state: Any) -> Dict[str, Any]:
    """Return the full runtime context used as rescheduler input."""

    active_plan_context = _active_plan_context_from_state(state)

    return {
        "mode": "revise",
        "plan_context": build_planner_context(state),
        "active_plan": active_plan_context,
        "work_item_progress": _work_item_progress_from_active_plan(active_plan_context),
    }

def render_reschedule_plan_context_message(contract: Dict[str, Any]) -> str:
    """Render the locked plan context as an authority reminder plus JSON."""

    compact_contract = json.dumps(contract, separators=(",", ":"), default=str)

    return (
        "[LOCKED RESCHEDULE CONTRACT]\n"
        "This contract defines the original planning agreement used to create the plan.\n"
        "Use it as the fixed authority for what the reschedule is allowed to preserve and repair.\n\n"

        "When repairing the schedule:\n"
        "- trust live plan truth for completed, partial, and remaining work\n"
        "- create future session contents only from live pending work inside the allowed contract scope\n"
        "- respect locked commitments, live time blocks, and fresh calendar blockers\n"
        "- schedule from current truth, not from the original full target\n\n"

        "You may change:\n"
        "- future session timing\n"
        "- future session order\n"
        "- grouping, splitting, or merging of remaining work\n"
        "- placement of pending work inside future sessions\n\n"

        "Contract JSON:\n"
        f"{compact_contract}\n\n"

        "Important reminder:\n"
        "This contract is not the current live status of the plan.\n"
        "It does not say what is already completed, still pending, moved, skipped, or blocked right now.\n"
        "Use the active plan snapshot and scheduling context supplied by runtime for current plan state and fresh calendar reality.\n\n"

        "When repairing the schedule:\n"
        "- trust live plan truth for remaining required hours\n"
        "- create future session contents only from live pending work that belongs to the allowed contract scope\n"
        "- respect live time_blocks and fresh calendar blockers\n"
        "- schedule from current truth, not from the original full target"
    )
