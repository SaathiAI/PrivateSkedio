"""Validate the local rescheduler dummy dataset against current models."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.models.intake import IntakeAgentOutput
from src.models.planner import StudyPlan
from src.services.planner_verifier import verify_plan


def read_json(name: str) -> dict:
    path = ROOT / "data_models" / name
    return json.loads(path.read_text(encoding="utf-8"))


def validate_active_plan_snapshot(snapshot: dict, intake_output: dict) -> None:
    if snapshot.get("has_plan") is not True:
        raise ValueError("active plan snapshot must set has_plan=true")

    plan_details = snapshot.get("plan_details") or {}
    if not plan_details.get("plan_id"):
        raise ValueError("active plan snapshot is missing plan_details.plan_id")
    if not isinstance(plan_details.get("days"), list) or not plan_details["days"]:
        raise ValueError("active plan snapshot must contain days")

    budget = ((plan_details.get("progress") or {}).get("work_item_budget")) or {}
    study_items = intake_output.get("study_items") or []
    expected_keys = {item["scope_reference_key"] for item in study_items}
    if set(budget.keys()) != expected_keys:
        raise ValueError("active plan progress keys do not match intake study_items")

    for key, item in budget.items():
        total = round(float(item.get("total") or 0), 2)
        spent = round(float(item.get("spent") or 0), 2)
        remaining = round(float(item.get("remaining") or 0), 2)
        if round(spent + remaining, 2) != total:
            raise ValueError(f"progress mismatch for {key}: spent + remaining != total")


def main() -> None:
    intake_output = read_json("rescheduler_demo_intake_output.json")
    scheduling_context = {
        "timezone": intake_output["availability"]["timezone"],
        "daily_study_hours": intake_output["availability"]["daily_study_hours"],
        "time_blocks": read_json("rescheduler_demo_commitments.json"),
        "calendar_blocks": read_json("rescheduler_demo_calendar_blocks.json"),
        "available_time_windows": read_json("rescheduler_demo_bundle.json")["scheduling_context"]["available_time_windows"],
    }
    study_plan = read_json("rescheduler_demo_plan.json")
    active_plan_snapshot = read_json("rescheduler_demo_active_plan_snapshot.json")

    IntakeAgentOutput.model_validate(intake_output)
    StudyPlan.model_validate(study_plan)

    verification = verify_plan(
        study_plan,
        {
            "goal": intake_output["goal"],
            "availability": intake_output["availability"],
            "study_items": intake_output["study_items"],
            "calendar_blocks": scheduling_context["calendar_blocks"],
            "available_time_windows": scheduling_context["available_time_windows"],
        },
        now="2026-06-24 05:00",
    )
    if not verification["passed"]:
        raise ValueError(json.dumps(verification, indent=2))

    validate_active_plan_snapshot(active_plan_snapshot, intake_output)

    print("Rescheduler demo fixtures validated successfully.")
    print(f"verified_plan_hours={verification['summary']['scheduled_total_hours']}")
    print(f"work_items={len(intake_output['study_items'])}")
    print(f"days={len(study_plan['days'])}")


if __name__ == "__main__":
    main()
