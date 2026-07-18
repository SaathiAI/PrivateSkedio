"""Router-only smoke tests for the Supervisor.

This intentionally runs only `supervisor_node`, not Intake, Planner, or the UI.

Usage:
    python scripts/router_only_test.py
    python scripts/router_only_test.py --case add_scope_during_review

The goal is fast routing diagnosis:
    fake state + latest user message -> Supervisor RoutingDecision
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGSMITH_TRACING"] = "false"

from langchain_core.messages import HumanMessage

from src.agents.envelope import make_envelope
from src.agents.supervisor_slop import supervisor_node

os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGSMITH_TRACING"] = "false"


@dataclass(frozen=True)
class RouterCase:
    name: str
    user_message: str
    expected_agent: str
    expected_intent: Optional[str] = None
    contract_ready: bool = False
    plan_verified: bool = False
    has_active_plan: bool = False
    draft_status: str = "none"
    planner_mode_hint: Optional[str] = None
    ui_context: Optional[Dict[str, Any]] = None
    worker_envelope: Optional[Dict[str, Any]] = None
    note: str = ""


def base_state(case: RouterCase) -> Dict[str, Any]:
    verified_plan = {"plan_id": "demo_verified_plan", "days": []} if case.plan_verified else None

    return {
        "pending_ui": None,
        "ui_context": case.ui_context,
        "ui_action": None,
        "user_id": "test_user_99",
        "messages": [HumanMessage(content=case.user_message)],
        "conversation_summary": None,
        "user_context": "",
        "has_active_plan": case.has_active_plan,
        "active_plan_id": "active_demo_plan" if case.has_active_plan else None,
        "active_plan_context": (
            {"has_plan": True, "plan_details": {"plan_id": "active_demo_plan"}}
            if case.has_active_plan
            else {"has_plan": False, "plan_details": None}
        ),
        "contract_ready": case.contract_ready,
        "draft_status": case.draft_status,
        "planner_mode_hint": case.planner_mode_hint,
        "routing_decision": None,
        "intake": None,
        "scheduling_context": None,
        "planner_status": "awaiting_approval" if case.plan_verified else None,
        "verified_plan": verified_plan,
        "committed": False,
        "worker_envelope": case.worker_envelope,
        "worker_outcome": None,
        "worker_hops_this_turn": 0,
        "final_reply": None,
    }


CASES = [
    RouterCase(
        name="new_plan",
        user_message="hi i wanna make a plan",
        expected_agent="intake",
        expected_intent="create_plan",
        contract_ready=False,
        note="New study contract belongs to Intake.",
    ),
    RouterCase(
        name="casual_chat",
        user_message="hi bro",
        expected_agent="user_facing",
        expected_intent="chat",
        contract_ready=False,
        note="Casual message should not wake Intake or Planner.",
    ),
    RouterCase(
        name="approve_verified_draft",
        user_message="approve",
        expected_agent="planner",
        expected_intent="approve_plan",
        contract_ready=True,
        plan_verified=True,
        draft_status="awaiting_review",
        planner_mode_hint="approve",
        note="Approval commits a verified draft through Planner.",
    ),
    RouterCase(
        name="change_hours_normal",
        user_message="increase daily hours to 6",
        expected_agent="intake",
        expected_intent="update_plan",
        contract_ready=True,
        plan_verified=True,
        draft_status="awaiting_review",
        planner_mode_hint="revise",
        note="Daily hours are Intake-owned availability.",
    ),
    RouterCase(
        name="add_scope_normal",
        user_message="add polynomials",
        expected_agent="intake",
        expected_intent="update_plan",
        contract_ready=True,
        plan_verified=True,
        draft_status="awaiting_review",
        planner_mode_hint="revise",
        note="Adding a chapter/scope belongs to Intake.",
    ),
    RouterCase(
        name="move_session_normal",
        user_message="move the Sunday session later",
        expected_agent="planner",
        expected_intent="update_plan",
        contract_ready=True,
        plan_verified=True,
        draft_status="awaiting_review",
        planner_mode_hint="revise",
        note="Changing timing/placement belongs to Planner.",
    ),
    RouterCase(
        name="change_hours_during_review",
        user_message="increase daily hours to 6",
        expected_agent="intake",
        expected_intent="update_plan",
        contract_ready=True,
        plan_verified=True,
        draft_status="awaiting_review",
        planner_mode_hint="revise",
        ui_context={"source": "pending_plan_review"},
        note=(
            "Important guardrail case: review feedback can still change "
            "Intake-owned availability."
        ),
    ),
    RouterCase(
        name="add_scope_during_review",
        user_message="hey can u add polynomials?",
        expected_agent="intake",
        expected_intent="update_plan",
        contract_ready=True,
        plan_verified=True,
        draft_status="awaiting_review",
        planner_mode_hint="revise",
        ui_context={"source": "pending_plan_review"},
        note=(
            "Important guardrail case: review feedback can still change "
            "Intake-owned scope."
        ),
    ),
    RouterCase(
        name="worker_question_to_user",
        user_message="yes",
        expected_agent="intake",
        expected_intent=None,
        contract_ready=False,
        worker_envelope=make_envelope(
            "intake",
            "pending",
            "Do you mean the exam is Monday 2026-07-20?",
            data={"intake_ready": False},
        ),
        note="A direct answer to an Intake clarification should continue Intake.",
    ),
]


async def run_case(case: RouterCase) -> Dict[str, Any]:
    state = base_state(case)
    result = await supervisor_node(deepcopy(state))
    decision = result.get("routing_decision")
    actual_agent = getattr(decision, "agent_chosen", None)
    actual_intent = getattr(decision, "intent", None)
    passed = actual_agent == case.expected_agent
    if case.expected_intent:
        passed = passed and actual_intent == case.expected_intent

    return {
        "case": case.name,
        "message": case.user_message,
        "expected_agent": case.expected_agent,
        "actual_agent": actual_agent,
        "expected_intent": case.expected_intent,
        "actual_intent": actual_intent,
        "confidence": getattr(decision, "confidence", None),
        "reasoning": getattr(decision, "reasoning", None),
        "passed": passed,
        "note": case.note,
    }


def print_result(row: Dict[str, Any]) -> None:
    mark = "PASS" if row["passed"] else "FAIL"
    print(f"\n[{mark}] {row['case']}")
    print(f"message: {row['message']}")
    print(f"expected: {row['expected_agent']} / {row['expected_intent']}")
    print(f"actual:   {row['actual_agent']} / {row['actual_intent']}")
    print(f"conf:     {row['confidence']}")
    print(f"reason:   {row['reasoning']}")
    if row["note"]:
        print(f"note:     {row['note']}")


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run Supervisor router-only smoke tests.")
    parser.add_argument("--case", dest="case_name", help="Run one case by name.")
    args = parser.parse_args()

    selected = CASES
    if args.case_name:
        selected = [case for case in CASES if case.name == args.case_name]
        if not selected:
            print("Unknown case. Available cases:")
            for case in CASES:
                print(f"- {case.name}")
            return 2

    rows = []
    for case in selected:
        rows.append(await run_case(case))
        print_result(rows[-1])

    passed = sum(1 for row in rows if row["passed"])
    total = len(rows)
    print(f"\nSummary: {passed}/{total} passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
