"""Helpers for planner draft review threads and email review links."""

from __future__ import annotations

from typing import Any, Dict, Optional
from urllib.parse import urlencode

from langchain_core.messages import AIMessage, HumanMessage


PLANNER_REVIEW_THREAD_KEY = "planner-review"


def scoped_thread_id(user_id: str, thread_id: Optional[str]) -> str:
    """Return the authenticated thread id used by the checkpointer."""

    raw_thread_id = (thread_id or "main").strip() or "main"
    safe_thread_id = raw_thread_id.replace(":", "_")
    return f"user:{user_id}:thread:{safe_thread_id}"


def build_review_link(
    *,
    base_url: str,
    thread_id: str = PLANNER_REVIEW_THREAD_KEY,
    action: str = "open",
) -> str:
    """Build one frontend review link for planner draft actions."""

    query = urlencode(
        {
            "review_thread": thread_id,
            "review_action": action,
        }
    )
    return f"{base_url.rstrip('/')}/?{query}"


def build_calendar_review_state(
    *,
    user_id: str,
    auto_message: str,
    review_reply: str,
    intake: Any,
    scheduling_context: Optional[Dict[str, Any]],
    active_plan_context: Optional[Dict[str, Any]],
    active_plan_id: Optional[str],
    verified_plan: Dict[str, Any],
    pending_ui: Dict[str, Any],
    user_context: str = "",
) -> Dict[str, Any]:
    """Return the supervisor state patch for one pending planner review."""

    return {
        "messages": [
            HumanMessage(content=auto_message),
            AIMessage(content=review_reply),
        ],
        "user_id": user_id,
        "user_context": user_context,
        "has_active_plan": bool(active_plan_context and active_plan_context.get("has_plan")),
        "active_plan_id": active_plan_id,
        "active_plan_context": active_plan_context,
        "contract_ready": bool(intake and getattr(intake, "status", None) == "approved"),
        "draft_status": "awaiting_review",
        "planner_mode_hint": "revise",
        "intake": intake,
        "scheduling_context": scheduling_context,
        "planner_status": "awaiting_approval",
        "verified_plan": verified_plan,
        "committed": False,
        "pending_ui": pending_ui,
        "ui_context": None,
        "ui_action": None,
        "worker_envelope": {
            "agent_name": "planner",
            "status": "awaiting_approval",
            "message": review_reply,
            "data": {
                "planner_status": "awaiting_approval",
                "committed": False,
                "has_verified_plan": True,
            },
        },
        "worker_outcome": None,
        "worker_hops_this_turn": 0,
        "final_reply": review_reply,
    }
