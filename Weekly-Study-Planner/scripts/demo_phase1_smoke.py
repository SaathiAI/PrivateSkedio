import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.api import routes


class FakeNeo:
    def __init__(self, state):
        self.state = state

    def get_active_plan_sessions(self, user_id):
        return self.state["active_plan_rows"]


def demo_active_plan_rows():
    return [
        {
            "plan_id": "demo_plan_001",
            "plan_status": "ACTIVE",
            "plan_total_hours": 6.0,
            "source": "planner",
            "work_item_targets": '{"Mathematics|Polynomials": 3.0, "Science|Light": 3.0}',
            "work_item_hours_spent": '{"Mathematics|Polynomials": 0.0, "Science|Light": 0.0}',
            "topic_time_estimates": '{"Mathematics|Polynomials": 3.0, "Science|Light": 3.0}',
            "intake_snapshot": '{"goal": "weekly_plan", "class": "10"}',
            "availability_math": '{"timezone": "Asia/Kolkata"}',
            "day_num": 1,
            "date": "2026-06-30",
            "capacity_hours": 3.0,
            "day_total_hours": 3.0,
            "session_id": "session_math_001",
            "session_title": "Polynomials practice",
            "session_type": "focused_chapter",
            "start_time": "18:00",
            "end_time": "21:00",
            "estimated_hours": 3.0,
            "allocated_hours": '[{"subject": "Mathematics", "chapter": "Polynomials", "hours": 3.0}]',
            "actual_time": 0.0,
            "session_status": "pending",
            "contents": [
                {
                    "match_key": "math|polynomials|zeros",
                    "canonical_name": "Zeros of a polynomial",
                    "subjects": ["Mathematics"],
                    "chapters": ["Polynomials"],
                    "type": "subtopic",
                    "status": "pending",
                    "time_spent": 0,
                }
            ],
            "completed_content_keys": [],
        },
        {
            "plan_id": "demo_plan_001",
            "plan_status": "ACTIVE",
            "plan_total_hours": 6.0,
            "source": "planner",
            "work_item_targets": '{"Mathematics|Polynomials": 3.0, "Science|Light": 3.0}',
            "work_item_hours_spent": '{"Mathematics|Polynomials": 0.0, "Science|Light": 0.0}',
            "topic_time_estimates": '{"Mathematics|Polynomials": 3.0, "Science|Light": 3.0}',
            "intake_snapshot": '{"goal": "weekly_plan", "class": "10"}',
            "availability_math": '{"timezone": "Asia/Kolkata"}',
            "day_num": 2,
            "date": "2026-07-01",
            "capacity_hours": 3.0,
            "day_total_hours": 3.0,
            "session_id": "session_science_001",
            "session_title": "Light revision",
            "session_type": "focused_chapter",
            "start_time": "17:00",
            "end_time": "20:00",
            "estimated_hours": 3.0,
            "allocated_hours": '[{"subject": "Science", "chapter": "Light", "hours": 3.0}]',
            "actual_time": 0.0,
            "session_status": "pending",
            "contents": [
                {
                    "match_key": "science|light|reflection",
                    "canonical_name": "Reflection of light",
                    "subjects": ["Science"],
                    "chapters": ["Light"],
                    "type": "subtopic",
                    "status": "pending",
                    "time_spent": 0,
                }
            ],
            "completed_content_keys": [],
        },
    ]


async def main():
    state = {"active_plan_rows": []}
    original_invoke = routes._invoke_supervisor_chat
    original_get_db = routes._get_db

    async def fake_invoke_supervisor_chat(thread_id, user_id, message, ui_action):
        if ui_action and ui_action.get("id") == "approve_demo_plan":
            state["active_plan_rows"] = demo_active_plan_rows()
            return routes.ChatResponse(
                thread_id=thread_id,
                reply="Plan saved. You can start with Maths tomorrow.",
                phase="planner",
                plan_committed=True,
                actions=[],
                draft_plan=None,
                pending_ui=None,
            )

        return routes.ChatResponse(
            thread_id=thread_id,
            reply="Here is your draft weekly plan.",
            phase="planner",
            plan_committed=False,
            actions=[routes.ChatActionOption(id="approve_demo_plan", label="Approve plan")],
            draft_plan={
                "plan_id": "demo_plan_001",
                "total_hours": 6.0,
                "days": [
                    {
                        "day_num": 1,
                        "date": "2026-06-30",
                        "total_hours": 3.0,
                        "capacity_hours": 3.0,
                        "sessions": [
                            {
                                "title": "Polynomials practice",
                                "start_time": "18:00",
                                "end_time": "21:00",
                            }
                        ],
                    }
                ],
            },
            pending_ui={"type": "plan_review"},
        )

    routes._invoke_supervisor_chat = fake_invoke_supervisor_chat
    routes._get_db = lambda: FakeNeo(state)

    try:
        draft = await routes.send_message(
            routes.ChatRequest(message="Make me a weekly class 10 study plan"),
            user_id="demo_student_001",
        )
        print("DRAFT_OK", draft.plan_committed is False, draft.draft_plan["plan_id"])

        committed = await routes.chat_action(
            routes.ChatActionRequest(action="approve_demo_plan"),
            user_id="demo_student_001",
        )
        print("COMMIT_OK", committed.plan_committed is True)

        active_plan = routes.get_active_plan_v2(user_id="demo_student_001")
        print("ACTIVE_PLAN_OK", active_plan["plan_id"], len(active_plan["days"]))

        allocation_summary = routes.get_allocation_summary(user_id="demo_student_001")
        print("ALLOCATION_OK", allocation_summary["plan_id"], len(allocation_summary["allocations"]))
    finally:
        routes._invoke_supervisor_chat = original_invoke
        routes._get_db = original_get_db


if __name__ == "__main__":
    asyncio.run(main())
