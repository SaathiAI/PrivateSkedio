"""Offline harness for exercising the current plan commit path.

Default mode patches Neo4j, calendar, and backlog sync with in-memory fakes, then
calls src.services.plan_commit.commit_study_plan with a demo StudyPlan. This is
for checking commit payload shape without touching real services.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import types
from pathlib import Path
from typing import Any, Dict, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class FakeGraph:
    def __init__(self):
        self.queries: List[Dict[str, Any]] = []

    def query(self, query, params=None):
        self.queries.append({"query": query, "params": params or {}})
        return [{"ok": True}]


class FakeNeo4jManager:
    def __init__(self):
        self.graph = FakeGraph()
        self.created_users: List[str] = []
        self.created_plans: List[Dict[str, Any]] = []
        self.resolved_content_batches: List[List[Dict[str, Any]]] = []
        self.created_sessions: List[Dict[str, Any]] = []
        self.content_links: List[Dict[str, Any]] = []

    def create_user(self, user_id):
        self.created_users.append(user_id)

    def generate_content_match_key(self, subject, chapter, content_name):
        raw = f"{subject}|{chapter}|{content_name}"
        return raw.lower().replace(" ", "_")

    def resolve_content_nodes(self, contents):
        self.resolved_content_batches.append(contents)
        return [content["match_key"] for content in contents if content.get("match_key")]

    def create_plan(
        self,
        user_id,
        plan_id,
        plan_name,
        start_date,
        planned_end_date,
        estimated_duration,
        total_hours,
        study_items=None,
        work_item_targets=None,
        work_item_hours_spent=None,
        intake_snapshot=None,
        availability_math=None,
        source="planner",
    ):
        record = {
            "user_id": user_id,
            "plan_id": plan_id,
            "plan_name": plan_name,
            "start_date": start_date,
            "planned_end_date": planned_end_date,
            "estimated_duration": estimated_duration,
            "total_hours": total_hours,
            "study_items": study_items,
            "work_item_targets": work_item_targets,
            "work_item_hours_spent": work_item_hours_spent,
            "intake_snapshot": intake_snapshot,
            "availability_math": availability_math,
            "source": source,
        }
        self.created_plans.append(record)
        return record

    def create_session_with_day_link(
        self,
        session_id,
        user_id,
        plan_id,
        day_date,
        title,
        session_type,
        date,
        start_time,
        end_time,
        estimated_hours,
        allocated_hours=None,
    ):
        self.created_sessions.append(
            {
                "session_id": session_id,
                "user_id": user_id,
                "plan_id": plan_id,
                "day_date": day_date,
                "title": title,
                "session_type": session_type,
                "date": date,
                "start_time": start_time,
                "end_time": end_time,
                "estimated_hours": estimated_hours,
                "allocated_hours": allocated_hours or [],
            }
        )
        return session_id

    def link_session_to_content_v2(
        self,
        session_id,
        content_match_key,
        status="pending",
        time_spent=0,
    ):
        self.content_links.append(
            {
                "session_id": session_id,
                "content_match_key": content_match_key,
                "status": status,
                "time_spent": time_spent,
            }
        )
        return True


class FakeCalendarClient:
    def __init__(self):
        self.deleted_ranges: List[Dict[str, Any]] = []
        self.created_plans: List[Dict[str, Any]] = []

    async def delete_saathi_events_in_range(self, time_min_iso, time_max_iso, user_id):
        self.deleted_ranges.append(
            {
                "time_min_iso": time_min_iso,
                "time_max_iso": time_max_iso,
                "user_id": user_id,
            }
        )
        return {"deleted": 0, "offline": True}

    async def create_events_from_plan(self, plan_json, user_id):
        self.created_plans.append({"plan_json": plan_json, "user_id": user_id})
        return {"created": len(json.loads(plan_json).get("days", [])), "offline": True}

    async def disconnect(self):
        return None


def install_offline_fakes():
    fake_neo4j = FakeNeo4jManager()
    fake_calendar = FakeCalendarClient()
    backlog_sync_calls: List[Dict[str, Any]] = []

    async def fake_sync_chapter_backlog_v2(user_id, neo4j=None):
        backlog_sync_calls.append({"user_id": user_id, "neo4j": neo4j})
        return {"success": True, "offline": True}

    fake_neo4j_module = types.ModuleType("src.database.neo4j")
    fake_neo4j_module.Neo4jManager = lambda: fake_neo4j
    sys.modules["src.database.neo4j"] = fake_neo4j_module

    fake_backlog_sync_module = types.ModuleType("src.services.backlog_sync")
    fake_backlog_sync_module.sync_chapter_backlog_v2 = fake_sync_chapter_backlog_v2
    sys.modules["src.services.backlog_sync"] = fake_backlog_sync_module

    fake_calendar_module = types.ModuleType("src.tools.test_mcp_client")
    fake_calendar_module.get_calendar_client = lambda: fake_calendar
    sys.modules["src.tools.test_mcp_client"] = fake_calendar_module

    return fake_neo4j, fake_calendar, backlog_sync_calls


def load_json(path: Optional[str]) -> Optional[Dict[str, Any]]:
    if not path:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def default_demo_plan() -> Dict[str, Any]:
    return {
        "plan_id": "plan_test_user_99_20260615_final",
        "total_hours": 10.0,
        "days": [
            {
                "day_num": 1,
                "date": "2026-06-15",
                "total_hours": 2.5,
                "capacity_hours": 2.5,
                "sessions": [
                    {
                        "title": "Quadratic Equations - methods + focused practice",
                        "session_type": "focused_chapter",
                        "start_time": "16:00",
                        "end_time": "17:30",
                        "estimated_hours": 1.5,
                        "allocated_hours": [
                            {
                                "subject": "Mathematics",
                                "chapter": "Quadratic Equations",
                                "hours": 1.5,
                            }
                        ],
                        "contents": [
                            {
                                "name": "Factoring concept + 6 practice problems",
                                "match_key": "mathematics_quadratic_factoring",
                                "subjects": ["Mathematics"],
                                "chapters": ["Quadratic Equations"],
                                "type": "practice",
                            },
                            {
                                "name": "Quadratic formula: 3 worked examples",
                                "match_key": "mathematics_quadratic_formula",
                                "subjects": ["Mathematics"],
                                "chapters": ["Quadratic Equations"],
                                "type": "topic",
                            },
                        ],
                        "reason": "Start hardest math backlog early with a concept-to-practice flow.",
                    },
                    {
                        "title": "Statistics - cumulative frequency patch",
                        "session_type": "chapter",
                        "start_time": "17:30",
                        "end_time": "18:30",
                        "estimated_hours": 1.0,
                        "allocated_hours": [
                            {
                                "subject": "Mathematics",
                                "chapter": "Statistics",
                                "hours": 1.0,
                            }
                        ],
                        "contents": [
                            {
                                "name": "Construct cumulative frequency table + 1 example",
                                "match_key": "mathematics_statistics_cumulative_frequency",
                                "subjects": ["Mathematics"],
                                "chapters": ["Statistics"],
                                "type": "subtopic",
                            }
                        ],
                        "reason": "Short patch task; avoid repeating mean, median, and mode.",
                    },
                ],
            },
            {
                "day_num": 2,
                "date": "2026-06-16",
                "total_hours": 1.5,
                "capacity_hours": 1.5,
                "sessions": [
                    {
                        "title": "Quadratic Equations - discriminant & practice set",
                        "session_type": "practice",
                        "start_time": "19:30",
                        "end_time": "21:00",
                        "estimated_hours": 1.5,
                        "allocated_hours": [
                            {
                                "subject": "Mathematics",
                                "chapter": "Quadratic Equations",
                                "hours": 1.5,
                            }
                        ],
                        "contents": [
                            {
                                "name": "Discriminant: identify roots + 8 exam-style problems",
                                "match_key": "mathematics_quadratic_discriminant",
                                "subjects": ["Mathematics"],
                                "chapters": ["Quadratic Equations"],
                                "type": "practice_target",
                            }
                        ],
                        "reason": "Practice-heavy block after the maths paper day.",
                    }
                ],
            },
            {
                "day_num": 3,
                "date": "2026-06-17",
                "total_hours": 3.0,
                "capacity_hours": 3.0,
                "sessions": [
                    {
                        "title": "Nationalism in India - movement timeline + SAQs",
                        "session_type": "chapter",
                        "start_time": "15:30",
                        "end_time": "17:00",
                        "estimated_hours": 1.5,
                        "allocated_hours": [
                            {
                                "subject": "Social Science",
                                "chapter": "Nationalism in India",
                                "hours": 1.5,
                            }
                        ],
                        "contents": [
                            {
                                "name": "Non-Cooperation & Civil Disobedience: timeline mapping",
                                "match_key": "sst_nationalism_non_cooperation_movement",
                                "subjects": ["Social Science"],
                                "chapters": ["Nationalism in India"],
                                "type": "topic",
                            },
                            {
                                "name": "Timed short-answer practice: 5 SAQs",
                                "match_key": "sst_nationalism_civil_disobedience",
                                "subjects": ["Social Science"],
                                "chapters": ["Nationalism in India"],
                                "type": "practice",
                            },
                        ],
                        "reason": "First-pass coverage split into timeline and active short-answer recall.",
                    },
                    {
                        "title": "Electricity - resistance numericals",
                        "session_type": "focused_chapter",
                        "start_time": "17:15",
                        "end_time": "18:45",
                        "estimated_hours": 1.5,
                        "allocated_hours": [
                            {
                                "subject": "Science",
                                "chapter": "Electricity",
                                "hours": 1.5,
                            }
                        ],
                        "contents": [
                            {
                                "name": "Resistance calculations: 3 worked examples + 4 practice problems",
                                "match_key": "science_electricity_resistance",
                                "subjects": ["Science"],
                                "chapters": ["Electricity"],
                                "type": "practice",
                            },
                            {
                                "name": "Intro to power: formula application",
                                "match_key": "science_electricity_power",
                                "subjects": ["Science"],
                                "chapters": ["Electricity"],
                                "type": "exercise",
                            },
                        ],
                        "reason": "Focus on remaining hard subtopics without re-teaching completed Ohm's law.",
                    }
                ],
            },
            {
                "day_num": 4,
                "date": "2026-06-18",
                "total_hours": 2.0,
                "capacity_hours": 2.0,
                "sessions": [
                    {
                        "title": "Statistics - ogive plotting & interpretation",
                        "session_type": "chapter",
                        "start_time": "15:00",
                        "end_time": "15:30",
                        "estimated_hours": 0.5,
                        "allocated_hours": [
                            {
                                "subject": "Mathematics",
                                "chapter": "Statistics",
                                "hours": 0.5,
                            }
                        ],
                        "contents": [
                            {
                                "name": "Ogive: plot + answer interpretation question",
                                "match_key": "mathematics_statistics_ogive",
                                "subjects": ["Mathematics"],
                                "chapters": ["Statistics"],
                                "type": "practice",
                            }
                        ],
                        "reason": "Small patch to finish Statistics on a lighter afternoon slot.",
                    },
                    {
                        "title": "Chemical Reactions - corrosion recall + applications",
                        "session_type": "focused_chapter",
                        "start_time": "19:30",
                        "end_time": "20:30",
                        "estimated_hours": 1.0,
                        "allocated_hours": [
                            {
                                "subject": "Science",
                                "chapter": "Chemical Reactions and Equations",
                                "hours": 1.0,
                            }
                        ],
                        "contents": [
                            {
                                "name": "Corrosion: 10-min recall + 4 application questions",
                                "match_key": "science_chem_corrosion",
                                "subjects": ["Science"],
                                "chapters": ["Chemical Reactions and Equations"],
                                "type": "practice",
                            }
                        ],
                        "reason": "Closure task: quick recall plus application practice after the dentist blocker.",
                    },
                    {
                        "title": "Electricity - power numerical wrap-up",
                        "session_type": "focused_chapter",
                        "start_time": "20:30",
                        "end_time": "21:00",
                        "estimated_hours": 0.5,
                        "allocated_hours": [
                            {
                                "subject": "Science",
                                "chapter": "Electricity",
                                "hours": 0.5,
                            }
                        ],
                        "contents": [
                            {
                                "name": "Power: 1 worked example + 1 practice problem",
                                "match_key": "science_electricity_power",
                                "subjects": ["Science"],
                                "chapters": ["Electricity"],
                                "type": "practice",
                            }
                        ],
                        "reason": "Short wrap-up to finish the Electricity target.",
                    },
                ],
            },
            {
                "day_num": 5,
                "date": "2026-06-19",
                "total_hours": 1.0,
                "capacity_hours": 3.5,
                "sessions": [
                    {
                        "title": "Nationalism in India - spaced recall & SAQ polish",
                        "session_type": "revision",
                        "start_time": "15:00",
                        "end_time": "16:00",
                        "estimated_hours": 1.0,
                        "allocated_hours": [
                            {
                                "subject": "Social Science",
                                "chapter": "Nationalism in India",
                                "hours": 1.0,
                            }
                        ],
                        "contents": [
                            {
                                "name": "Short-answer recall + timeline quick review",
                                "match_key": "sst_nationalism_sense_of_collective_belonging",
                                "subjects": ["Social Science"],
                                "chapters": ["Nationalism in India"],
                                "type": "revision_target",
                            }
                        ],
                        "reason": "Spaced review to consolidate Nationalism across two days.",
                    }
                ],
            },
            {
                "day_num": 6,
                "date": "2026-06-20",
                "total_hours": 0.0,
                "capacity_hours": 2.5,
                "sessions": [],
            },
        ],
        "creation_reason": "Verified planner output from convo_create_plan_3cfd528a.",
    }


def extract_plan(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not payload:
        return default_demo_plan()
    return payload.get("plan") or payload


def derive_commit_metadata(intake_payload: Optional[Dict[str, Any]]):
    if not intake_payload:
        return {}, [], {}

    from src.models.intake import IntakeAgentOutput

    intake = IntakeAgentOutput.model_validate(intake_payload)
    targets = {
        item.scope_reference_key or item.chapter: round(float(item.estimated_hours), 2)
        for item in intake.study_items
    }
    backlog_keys = []
    for item in intake.study_items:
        for key in item.remaining_subtopics:
            if key not in backlog_keys:
                backlog_keys.append(key)
    return targets, backlog_keys, intake.model_dump()


async def main():
    parser = argparse.ArgumentParser(description="Run a demo plan through commit_study_plan.")
    parser.add_argument("--user-id", default="claude-mythos")
    parser.add_argument("--plan-json", help="StudyPlan JSON or PlannerOutput JSON containing plan.")
    parser.add_argument(
        "--intake-json",
        default=str(PROJECT_ROOT / "data_models" / "intake_data_model.json"),
        help="Intake JSON used for work targets and intake_snapshot.",
    )
    parser.add_argument(
        "--real",
        action="store_true",
        help="Use real Neo4j/calendar/backlog services. Default is offline fakes.",
    )
    parser.add_argument(
        "--no-backlog-wait",
        action="store_true",
        help="Schedule backlog sync in background instead of waiting.",
    )
    parser.add_argument(
        "--show-side-effects",
        action="store_true",
        help="Print fake Neo4j/calendar side effects in offline mode.",
    )
    args = parser.parse_args()

    fake_neo4j = fake_calendar = backlog_sync_calls = None
    if not args.real:
        fake_neo4j, fake_calendar, backlog_sync_calls = install_offline_fakes()

    from src.models.planner import StudyPlan
    from src.services.plan_commit import commit_study_plan

    plan_payload = load_json(args.plan_json)
    intake_payload = load_json(args.intake_json)
    work_item_targets, backlog_keys, intake_snapshot = derive_commit_metadata(intake_payload)

    plan = StudyPlan.model_validate(extract_plan(plan_payload))
    print(
        json.dumps(
            {
                "mode": "real" if args.real else "offline",
                "user_id": args.user_id,
                "plan_id": plan.plan_id,
                "days": len(plan.days or []),
                "sessions": sum(len(day.sessions) for day in plan.days or []),
                "wait_for_backlog_sync": not args.no_backlog_wait,
            },
            indent=2,
        ),
        flush=True,
    )

    result = await commit_study_plan(
        user_id=args.user_id,
        plan=plan,
        work_item_targets=work_item_targets,
        backlog_match_keys=backlog_keys,
        intake_snapshot=intake_snapshot,
        wait_for_backlog_sync=not args.no_backlog_wait,
    )

    print("\nCOMMIT RETURNED", flush=True)
    print(json.dumps(result, indent=2, default=str), flush=True)

    if not args.real and args.show_side_effects:
        print("\nOFFLINE SIDE EFFECTS", flush=True)
        print(
            json.dumps(
                {
                    "created_users": fake_neo4j.created_users,
                    "created_plans": fake_neo4j.created_plans,
                    "created_sessions": fake_neo4j.created_sessions,
                    "content_links": fake_neo4j.content_links,
                    "calendar_deleted_ranges": fake_calendar.deleted_ranges,
                    "calendar_created_plans": fake_calendar.created_plans,
                    "backlog_sync_calls": backlog_sync_calls,
                    "day_queries": fake_neo4j.graph.queries,
                },
                indent=2,
                default=str,
            ),
            flush=True,
        )


if __name__ == "__main__":
    asyncio.run(main())
