from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import uuid
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("LANGSMITH_TRACING", "false")
os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")

from src.agents.planner_agent import (  # noqa: E402
    CanonicalItems,
    PlannerState,
    UserProfile,
    create_planner_graph,
)


REPORT_DIR = ROOT / "logs" / "planner_evals"


def base_profile() -> dict[str, Any]:
    return {
        "subject": ["Mathematics"],
        "plan_start": "2026-05-31",
        "plan_end": "2026-06-05",
        "deadline_datetime": "2026-06-05T14:00:00+05:30",
        "notes": (
            "Finish and practice Quadratic Equations and Polynomials. "
            "Mixed sessions with an evening bias, 30-50 minute gaps between topic blocks, "
            "and light review only right before the exam."
        ),
        "daily_study_hours": {
            "2026-05-31": 3.0,
            "2026-06-01": 3.0,
            "2026-06-02": 3.0,
            "2026-06-03": 3.0,
            "2026-06-04": 3.0,
            "2026-06-05": 1.5,
        },
        "scheduling_contract": {
            "timezone": "Asia/Calcutta",
            "raw_free_windows": {
                "2026-05-31": {
                    "day_label": "Sunday",
                    "windows": [
                        {"start_time": "07:00", "end_time": "13:00"},
                        {"start_time": "15:00", "end_time": "23:00"},
                    ],
                    "free_minutes": 840,
                    "note": "Family lunch 13:00-15:00 blocks midday.",
                },
                "2026-06-01": {
                    "day_label": "Monday",
                    "windows": [
                        {"start_time": "07:00", "end_time": "08:00"},
                        {"start_time": "14:00", "end_time": "23:00"},
                    ],
                    "free_minutes": 600,
                },
                "2026-06-02": {
                    "day_label": "Tuesday",
                    "windows": [
                        {"start_time": "07:00", "end_time": "08:00"},
                        {"start_time": "14:00", "end_time": "17:00"},
                        {"start_time": "18:00", "end_time": "23:00"},
                    ],
                    "free_minutes": 540,
                },
                "2026-06-03": {
                    "day_label": "Wednesday",
                    "windows": [
                        {"start_time": "07:00", "end_time": "08:00"},
                        {"start_time": "14:00", "end_time": "23:00"},
                    ],
                    "free_minutes": 600,
                },
                "2026-06-04": {
                    "day_label": "Thursday",
                    "windows": [
                        {"start_time": "07:00", "end_time": "08:00"},
                        {"start_time": "14:00", "end_time": "17:00"},
                        {"start_time": "18:00", "end_time": "23:00"},
                    ],
                    "free_minutes": 540,
                },
                "2026-06-05": {
                    "day_label": "Friday - exam day",
                    "windows": [
                        {
                            "start_time": "07:00",
                            "end_time": "08:00",
                            "note": "Light revision only before school.",
                        }
                    ],
                    "free_minutes": 60,
                    "note": "Exam starts at 14:00. Only 07:00-08:00 is usable.",
                },
            },
            "soft_constraints": {
                "preferred_slot_style": "mixed",
                "slot_bias": "evening",
                "break_gap_minutes": {"min": 30, "max": 50},
                "avoid_tiny_sessions_under_minutes": 45,
                "avoid_late_night_after": "21:30",
                "buffer_after_school_minutes": 30,
                "notes": [],
            },
        },
    }


def base_canonical() -> dict[str, Any]:
    return {
        "allocation_groups": [
            {
                "allocation_group_id": "Mathematics::Quadratic Equations",
                "subject": "Mathematics",
                "chapter": "Quadratic Equations",
                "target_minutes": 540,
                "priority": "high",
                "confidence": "medium_high",
                "covered_backlog_match_keys": [
                    "mathematics.quadratic_equations.factorisation",
                    "mathematics.quadratic_equations.quadratic_formula",
                    "mathematics.quadratic_equations.discriminant",
                ],
                "planning_guidance": [
                    "Start with factorisation and equation setup.",
                    "Move to quadratic formula and discriminant.",
                    "End with timed word-problem practice.",
                ],
            },
            {
                "allocation_group_id": "Mathematics::Polynomials",
                "subject": "Mathematics",
                "chapter": "Polynomials",
                "target_minutes": 420,
                "priority": "medium",
                "confidence": "medium_high",
                "covered_backlog_match_keys": [
                    "mathematics.polynomials.zeros",
                    "mathematics.polynomials.coefficients_relationship",
                ],
                "planning_guidance": [
                    "Cover zeros and their interpretation first.",
                    "Practice relationships between zeros and coefficients.",
                    "Add graphical interpretation near the end.",
                ],
            },
        ],
        "pending_backlog_items": [
            {
                "backlog_match_key": "mathematics.quadratic_equations.factorisation",
                "subject": "Mathematics",
                "chapter": "Quadratic Equations",
                "subtopic": "Solving by factorisation",
                "status": "pending",
                "source": "neo4j",
            },
            {
                "backlog_match_key": "mathematics.quadratic_equations.quadratic_formula",
                "subject": "Mathematics",
                "chapter": "Quadratic Equations",
                "subtopic": "Quadratic formula",
                "status": "pending",
                "source": "neo4j",
            },
            {
                "backlog_match_key": "mathematics.quadratic_equations.discriminant",
                "subject": "Mathematics",
                "chapter": "Quadratic Equations",
                "subtopic": "Nature of roots using discriminant",
                "status": "weak",
                "source": "neo4j",
            },
            {
                "backlog_match_key": "mathematics.polynomials.zeros",
                "subject": "Mathematics",
                "chapter": "Polynomials",
                "subtopic": "Zeros of a polynomial",
                "status": "pending",
                "source": "neo4j",
            },
            {
                "backlog_match_key": "mathematics.polynomials.coefficients_relationship",
                "subject": "Mathematics",
                "chapter": "Polynomials",
                "subtopic": "Relationship between zeros and coefficients",
                "status": "weak",
                "source": "neo4j",
            },
        ],
        "excluded_backlog_items": [],
    }


def fixtures() -> dict[str, dict[str, Any]]:
    tight_profile = base_profile()
    tight_canonical = base_canonical()

    relaxed_profile = deepcopy(tight_profile)
    relaxed_profile["deadline_datetime"] = None
    relaxed_profile["plan_end"] = "2026-06-07"
    relaxed_profile["notes"] = "Relaxed practice plan. Keep sessions humane and avoid late nights."
    relaxed_profile["daily_study_hours"] = {
        "2026-05-31": 1.5,
        "2026-06-01": 1.5,
        "2026-06-02": 1.5,
        "2026-06-03": 1.5,
        "2026-06-04": 1.5,
        "2026-06-05": 1.5,
        "2026-06-06": 2.0,
        "2026-06-07": 2.0,
    }
    relaxed_profile["scheduling_contract"]["raw_free_windows"]["2026-06-06"] = {
        "day_label": "Saturday",
        "windows": [{"start_time": "10:00", "end_time": "13:00"}],
        "free_minutes": 180,
    }
    relaxed_profile["scheduling_contract"]["raw_free_windows"]["2026-06-07"] = {
        "day_label": "Sunday",
        "windows": [{"start_time": "10:00", "end_time": "13:00"}],
        "free_minutes": 180,
    }
    relaxed_canonical = deepcopy(tight_canonical)
    relaxed_canonical["allocation_groups"][0]["target_minutes"] = 240
    relaxed_canonical["allocation_groups"][1]["target_minutes"] = 180

    multi_profile = deepcopy(tight_profile)
    multi_profile["subject"] = ["Mathematics", "Science"]
    multi_profile["deadline_datetime"] = "2026-06-04T10:00:00+05:30"
    multi_profile["notes"] = (
        "Two assessments: Science practical checkpoint on 2026-06-03 morning, "
        "Math test on 2026-06-04 at 10:00. Prioritize earlier deadline first."
    )
    multi_profile["plan_end"] = "2026-06-04"
    multi_profile["daily_study_hours"] = {
        "2026-05-31": 2.0,
        "2026-06-01": 2.0,
        "2026-06-02": 2.5,
        "2026-06-03": 2.0,
        "2026-06-04": 1.0,
    }
    multi_canonical = {
        "allocation_groups": [
            {
                "allocation_group_id": "Science::Electricity",
                "subject": "Science",
                "chapter": "Electricity",
                "target_minutes": 240,
                "priority": "high",
                "planning_guidance": ["Finish this before the earlier practical checkpoint."],
            },
            {
                "allocation_group_id": "Mathematics::Quadratic Equations",
                "subject": "Mathematics",
                "chapter": "Quadratic Equations",
                "target_minutes": 330,
                "priority": "high",
                "planning_guidance": ["Use mixed problem practice near the end."],
            },
        ],
        "pending_backlog_items": [],
    }

    uneven_profile = deepcopy(tight_profile)
    uneven_profile["notes"] = "Energy is low after school. Prefer one hard session on weekend and lighter weekday review."
    uneven_profile["daily_study_hours"] = {
        "2026-05-31": 4.0,
        "2026-06-01": 1.0,
        "2026-06-02": 1.0,
        "2026-06-03": 2.0,
        "2026-06-04": 1.5,
        "2026-06-05": 1.0,
    }
    uneven_canonical = deepcopy(tight_canonical)
    uneven_canonical["allocation_groups"][0]["target_minutes"] = 360
    uneven_canonical["allocation_groups"][1]["target_minutes"] = 270

    impossible_profile = deepcopy(tight_profile)
    impossible_profile["daily_study_hours"] = {
        "2026-05-31": 1.0,
        "2026-06-01": 1.0,
        "2026-06-02": 1.0,
    }
    impossible_profile["plan_end"] = "2026-06-02"
    impossible_profile["deadline_datetime"] = "2026-06-02T22:00:00+05:30"
    impossible_canonical = deepcopy(tight_canonical)
    impossible_canonical["allocation_groups"][0]["target_minutes"] = 360
    impossible_canonical["allocation_groups"][1]["target_minutes"] = 240

    return {
        "tight_exam": {
            "profile": tight_profile,
            "canonical": tight_canonical,
            "user_context": "",
        },
        "relaxed_practice": {
            "profile": relaxed_profile,
            "canonical": relaxed_canonical,
            "user_context": "Student prefers calm consistency over cramming.",
        },
        "multiple_deadlines": {
            "profile": multi_profile,
            "canonical": multi_canonical,
            "user_context": "Student gets anxious near deadlines; earlier wins should reduce stress.",
        },
        "uneven_energy": {
            "profile": uneven_profile,
            "canonical": uneven_canonical,
            "user_context": "Student tires quickly after school and does better with hard work on weekends.",
        },
        "impossible_scope": {
            "profile": impossible_profile,
            "canonical": impossible_canonical,
            "user_context": "This should ask for a constraint change instead of hallucinating a plan.",
        },
    }


def iter_sessions(plan: Any):
    if not plan:
        return
    for day in plan.days:
        for session in day.sessions:
            yield day, session


def score_result(case_name: str, run_index: int, result: dict[str, Any]) -> dict[str, Any]:
    verify = result.get("verify_errors") or {}
    plan = result.get("candidate_plan") or result.get("verified_plan")
    sessions = list(iter_sessions(plan)) if plan else []
    durations = [float(session.estimated_hours or 0) for _day, session in sessions]
    mixed = [
        session
        for _day, session in sessions
        if (session.session_type or "").lower() == "mixed"
        or len(session.allocated_hours or []) > 1
    ]
    long_sessions = [session for _day, session in sessions if float(session.estimated_hours or 0) >= 2.5]
    late_sessions = [session for _day, session in sessions if (session.end_time or "") > "21:30"]

    quality_flags = []
    if long_sessions:
        quality_flags.append(f"{len(long_sessions)} sessions are >=2.5h")
    if sessions and len(mixed) / len(sessions) > 0.6:
        quality_flags.append("mixed-session ratio is high")
    if late_sessions:
        quality_flags.append(f"{len(late_sessions)} sessions end after 21:30")
    if plan and len(sessions) <= len(plan.days):
        quality_flags.append("mostly one session per day")

    return {
        "case": case_name,
        "run": run_index,
        "passed_verifier": verify.get("status") == "PASSED",
        "needs_input": result.get("candidate_plan") is None and result.get("verified_plan") is None,
        "verify_status": verify.get("status"),
        "verify_errors": verify.get("hour_errors", []),
        "candidate_plan_id": getattr(plan, "plan_id", None) if plan else None,
        "total_sessions": len(sessions),
        "total_hours": round(sum(durations), 2),
        "avg_session_hours": round(statistics.mean(durations), 2) if durations else 0,
        "max_session_hours": round(max(durations), 2) if durations else 0,
        "mixed_sessions": len(mixed),
        "long_sessions": len(long_sessions),
        "late_sessions": len(late_sessions),
        "quality_flags": quality_flags,
    }


async def run_case(
    case_name: str,
    case: dict[str, Any],
    run_index: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    app = create_planner_graph()
    state = PlannerState(
        user_id=f"eval_{case_name}_{run_index}_{uuid.uuid4().hex[:6]}",
        user_profile=UserProfile(**case["profile"]),
        canonical_items=CanonicalItems(**case["canonical"]),
        intake_output={"fixture": case_name},
        budget_feasibility=None,
        action="create_plan",
        messages=[HumanMessage(content=f"Planner evaluation fixture: {case_name}")],
        approval_status=None,
        final_plan_id=None,
        committed=False,
        old_plan_id=None,
        user_context=case.get("user_context") or "",
        clashes=None,
    )
    try:
        result = await asyncio.wait_for(app.ainvoke(state), timeout=timeout_seconds)
    except Exception as exc:
        return {
            "case": case_name,
            "run": run_index,
            "passed_verifier": False,
            "needs_input": False,
            "verify_status": None,
            "error": f"{type(exc).__name__}: {exc}",
            "quality_flags": ["runner_error"],
        }
    return score_result(case_name, run_index, result)


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run SkedioAI Planner quality evaluations.")
    parser.add_argument("--fixture", action="append", help="Fixture name. Can be repeated.")
    parser.add_argument("--runs", type=int, default=1, help="Runs per fixture.")
    parser.add_argument("--timeout", type=int, default=180, help="Per-run timeout in seconds.")
    parser.add_argument("--list", action="store_true", help="List fixtures and exit.")
    args = parser.parse_args()

    all_fixtures = fixtures()
    if args.list:
        for name in sorted(all_fixtures):
            print(name)
        return 0

    selected = args.fixture or list(all_fixtures.keys())
    unknown = [name for name in selected if name not in all_fixtures]
    if unknown:
        raise SystemExit(f"Unknown fixtures: {', '.join(unknown)}")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "created_at": datetime.now().isoformat(),
        "runs_per_fixture": args.runs,
        "model": "configured in src.agents.planner_agent",
        "results": [],
    }

    for name in selected:
        for run_index in range(1, args.runs + 1):
            print(f"\n=== Running {name} #{run_index} ===")
            scored = await run_case(name, all_fixtures[name], run_index, args.timeout)
            report["results"].append(scored)
            print(json.dumps(scored, indent=2, default=str))

    total = len(report["results"])
    passed = sum(1 for item in report["results"] if item["passed_verifier"])
    report["summary"] = {
        "total_runs": total,
        "passed_verifier": passed,
        "pass_rate": round(passed / total, 2) if total else 0,
        "quality_flags": {
            flag: sum(flag in item["quality_flags"] for item in report["results"])
            for flag in sorted({flag for item in report["results"] for flag in item["quality_flags"]})
        },
    }

    out_path = REPORT_DIR / f"planner_eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print("\n=== Summary ===")
    print(json.dumps(report["summary"], indent=2))
    print(f"\nReport: {out_path}")
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(exit_code)
