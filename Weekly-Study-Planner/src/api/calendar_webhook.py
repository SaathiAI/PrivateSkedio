"""
calendar_webhook.py
===================
Google Calendar webhook handler for SkedioAI.

Flow:
  Google Calendar → POST /calendar/webhook
    → detect clash with active SkedioAI sessions
    → invoke planner in auto_mode
    → clean fix  → auto-commit + success email
    → overflow   → conflict email → STOP

Add to routes.py:
    from src.api.calendar_webhook import webhook_router
    app.include_router(webhook_router)

Register webhook once:
    asyncio.run(register_calendar_webhook("https://YOUR_NGROK_URL/calendar/webhook", user_id="your-user-id"))
"""

import json
import logging
import asyncio
import os
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Request, BackgroundTasks
from langchain_core.messages import HumanMessage

from src.database.neo4j import Neo4jManager
from src.tools.test_mcp_client import get_calendar_client
from src.mcp_servers.email_mcp_server import _send_alert_email as _send_conflict_email
from src.mcp_servers.email_mcp_server import send_plan_review_email
from src.api.user_email import get_user_alert_email
from src.services.active_plan import get_active_plan_snapshot
from src.agents.planner_agent import (
    create_planner_graph,
    planner_state_from_input,
)
from src.models.intake import IntakeAgentOutput
from src.models.planner import PlannerRequest, StudyPlan
from src.services.intake_contract_validator import (
    _build_available_time_windows,
    _build_scheduling_context,
)
from src.services.review_flow import (
    PLANNER_REVIEW_THREAD_KEY,
    build_calendar_review_state,
    build_review_link,
)
from src.services.user_memory import build_runtime_user_context

logger = logging.getLogger(__name__)

webhook_router = APIRouter()

# Legacy single-user fallback (set SAATHI_WEBHOOK_USER_ID only for old single-user deploys)
_FALLBACK_USER_ID = os.getenv("SAATHI_WEBHOOK_USER_ID", "")
ALERT_EMAIL = os.getenv("SAATHI_ALERT_EMAIL", "")

# channel_id → user_id mapping (populated by register_calendar_webhook)
_channel_user_map: dict[str, str] = {}

# Cache to avoid processing same event twice
_processed_events: set = set()


# ─────────────────────────────────────────────
# Multi-User Resolution
# ─────────────────────────────────────────────

def _resolve_user_from_channel(channel_id: str) -> Optional[str]:
    """Resolve user_id from webhook channel mapping, with env fallback."""
    user_id = _channel_user_map.get(channel_id)
    if user_id:
        return user_id
    if _FALLBACK_USER_ID:
        return _FALLBACK_USER_ID
    return None


def _resolve_user_from_event(event: dict) -> Optional[str]:
    """Try to extract user_id from a calendar event's extendedProperties."""
    props = event.get("extendedProperties", {}).get("private", {})
    return props.get("user_id")


# ─────────────────────────────────────────────
# Email Helpers
# ─────────────────────────────────────────────

def _resolve_webhook_recipient(user_id: str) -> Optional[str]:
    """Prefer the user's configured alert email, with env fallback for legacy setups."""

    try:
        recipient = get_user_alert_email(user_id)
        if recipient:
            return recipient
    except Exception as exc:
        logger.warning("Webhook recipient lookup failed for user %s: %s", user_id, exc)

    if ALERT_EMAIL:
        return ALERT_EMAIL

    return None


def send_review_email(
    *,
    user_id: str,
    sessions: list[dict[str, Any]],
    new_event_title: str,
    agent_response: str = "",
):
    """Send a planner-review email with links into the normal website flow."""

    recipient = _resolve_webhook_recipient(user_id)
    if not recipient:
        logger.warning("No webhook alert recipient available for user %s; skipping review email", user_id)
        return

    frontend_base = os.getenv("FRONTEND_URL", "https://saathi-frontend-fplr.onrender.com")
    open_url = build_review_link(base_url=frontend_base, thread_id=PLANNER_REVIEW_THREAD_KEY, action="open")
    approve_url = build_review_link(base_url=frontend_base, thread_id=PLANNER_REVIEW_THREAD_KEY, action="approve_plan")
    request_changes_url = build_review_link(base_url=frontend_base, thread_id=PLANNER_REVIEW_THREAD_KEY, action="request_changes")

    send_plan_review_email(
        recipient=recipient,
        subject_line="SkedioAI: your study plan was adjusted",
        intro=f'Your calendar changed because of "{new_event_title}", so I prepared an updated study draft for you to review.',
        sessions=sessions,
        agent_response=agent_response,
        approve_url=approve_url,
        request_changes_url=request_changes_url,
        open_url=open_url,
    )
    logger.info("📧 Review email sent to %s", recipient)


def send_conflict_email(
    clashes: list,
    new_event_title: str,
    *,
    user_id: str,
    agent_response: str = "",
):
    
    """Email user when auto-reschedule failed — needs manual action."""
    recipient = _resolve_webhook_recipient(user_id)
    if not recipient:
        logger.warning("No webhook alert recipient available for user %s; skipping conflict email", user_id)
        return

    sessions = [{
        "title": c["title"],
        "start": f"{c['date']} {c['start']}",
        "end": f"{c['date']} {c['end']}"
    } for c in clashes]


    try:
        _send_conflict_email(missed_events=sessions, recipient=recipient,agent_response=agent_response)
        logger.info("📧 Conflict email sent to %s", recipient)
    except Exception as e:
        logger.error(f"❌ Conflict email failed: {e}")


# ─────────────────────────────────────────────
# Clash Detection
# ─────────────────────────────────────────────

def detect_clash(new_event: dict, active_plan: dict) -> list:
    """
    new_event format (from get_non_skedioai_events_core):
    {"date": "2026-02-24", "start_time": "21:15", "end_time": "22:15", "title": "Lunch"}

    active_plan format:
    {"plan_id": ..., "days": [{"date": ..., "sessions": [...]}]}
    """
    clashes = []

    try:
        new_start = datetime.strptime(f"{new_event['date']} {new_event['start_time']}", "%Y-%m-%d %H:%M")
        new_end = datetime.strptime(f"{new_event['date']} {new_event['end_time']}", "%Y-%m-%d %H:%M")
        
       
    except Exception as e:
        logger.error(f"Failed to parse new event times: {e}")
        return clashes

    for day in active_plan.get("days", []):
        if day["date"] != new_event["date"]:
            continue  # only check same day

        for session in day.get("sessions", []):
            if session.get("status") == "done":
                continue  # skip done sessions

            try:
                session_start = datetime.strptime(f"{day['date']} {session['start_time']}", "%Y-%m-%d %H:%M")
                session_end = datetime.strptime(f"{day['date']} {session['end_time']}", "%Y-%m-%d %H:%M")
            except Exception:
                continue

            # Overlap check: not (new_end <= session_start or new_start >= session_end)
            if not (new_end <= session_start or new_start >= session_end):
                contents = session.get("contents") or []
                first_content = contents[0] if contents else {}
                subject = ((first_content.get("subjects") or ["General"])[0] if isinstance(first_content, dict) else "General") or "General"
                topic = session.get("title") or (first_content.get("name") if isinstance(first_content, dict) else None) or "Study Session"
                clashes.append({
                    "match_key": session.get("session_id"),
                    "topic": topic,
                    "subject": subject,
                    "date": day["date"],
                    "start": session["start_time"],
                    "end": session["end_time"],
                    "title": f"{subject} - {topic}",
                })

    return clashes


# ─────────────────────────────────────────────
# Auto-Reschedule
# ─────────────────────────────────────────────

async def trigger_auto_reschedule(clashes: list, new_event_title: str, active_plan_id: str, user_id: str):
    """Invoke planner in auto_mode to silently fix clash."""
    logger.info(f"🤖 Auto-reschedule triggered for {len(clashes)} clash(es) for user {user_id}")

    clash_descriptions = "\n".join([
        f"- {c['subject']} {c['topic']} on {c['date']} {c['start']}-{c['end']}"
        for c in clashes
    ])

    user_context = await build_runtime_user_context(
        user_id=user_id,
        query="calendar clash study preferences constraints recent plan behavior",
    )

    auto_message = f"""Auto-reschedule triggered. auto_reschedule:true

You added: "{new_event_title}" which conflicted with your plan.

Conflicting sessions:
{clash_descriptions}

Please revise only future incomplete sessions using the fresh calendar context.
Keep the same intake contract unless reality no longer supports it.
Return a clean revised draft for user review. Do not auto-commit.

user_id = {user_id}"""

    active_plan_snapshot = get_active_plan_snapshot(user_id, force_refresh=True)
    planner_request = _build_reschedule_request_from_active_plan(
        user_id=user_id,
        active_plan_snapshot=active_plan_snapshot,
    )

    draft_state = planner_state_from_input(
        planner_request,
        commit_requested=False,
        messages=[HumanMessage(content=auto_message)],
        user_context=user_context,
        has_active_plan=True,
        active_plan_id=active_plan_id,
    )
    draft_state.auto_mode = True
    draft_state.has_overflow = False
    draft_state.clashes = clashes

    graph = create_planner_graph()
    result = await graph.ainvoke(draft_state)

    agent_response=result['messages'][-1].content

    has_overflow = result.get("has_overflow", False)
    planner_status = result.get("planner_status", "")
    verified_plan = result.get("verified_plan")

    if isinstance(verified_plan, dict):
        verified_plan = StudyPlan.model_validate(verified_plan)

    if isinstance(verified_plan, StudyPlan) and planner_status == "awaiting_approval":
        await _store_pending_review(
            user_id=user_id,
            auto_message=auto_message,
            review_reply=agent_response,
            planner_request=planner_request,
            active_plan_id=active_plan_id,
            verified_plan=verified_plan.model_dump(),
        )
        send_review_email(
            user_id=user_id,
            sessions=_review_sessions_from_plan(verified_plan),
            new_event_title=new_event_title,
            agent_response=agent_response,
        )
        return

    if has_overflow or planner_status == "escalate":
        logger.info("⚠️ Auto-reschedule failed — escalating")
        send_conflict_email(clashes, new_event_title, user_id=user_id, agent_response=agent_response)
    else:
        logger.warning("⚠️ Unknown state — sending conflict email as fallback")
        send_conflict_email(clashes, new_event_title, user_id=user_id, agent_response=agent_response)


def _review_sessions_from_plan(plan: StudyPlan) -> list[dict[str, str]]:
    """Flatten one reviewable plan into email-friendly session rows."""

    sessions: list[dict[str, str]] = []
    for day in plan.days:
        for session in day.sessions:
            sessions.append(
                {
                    "title": session.title or "Study Session",
                    "start": f"{day.date} {session.start_time}",
                    "end": f"{day.date} {session.end_time}",
                }
            )
    return sessions


async def _store_pending_review(
    *,
    user_id: str,
    auto_message: str,
    review_reply: str,
    planner_request: PlannerRequest,
    active_plan_id: str,
    verified_plan: dict[str, Any],
) -> None:
    """Store this calendar-made draft in the normal supervisor review thread."""

    from src.api.routes import _checkpointer, get_supervisor_graph
    from src.agents.supervisor_slop import PLAN_REVIEW_ACTIONS
    from src.services.review_flow import scoped_thread_id

    app_graph = get_supervisor_graph(_checkpointer)
    thread_id = scoped_thread_id(user_id, PLANNER_REVIEW_THREAD_KEY)
    state_patch = build_calendar_review_state(
        user_id=user_id,
        auto_message=auto_message,
        review_reply=review_reply,
        intake=planner_request.intake,
        scheduling_context=planner_request.scheduling_context,
        active_plan_context=planner_request.active_plan_context,
        active_plan_id=active_plan_id,
        verified_plan=verified_plan,
        pending_ui={"type": "plan_review", "actions": list(PLAN_REVIEW_ACTIONS)},
        user_context="",
    )
    await app_graph.aupdate_state(
        {"configurable": {"thread_id": thread_id}},
        state_patch,
        as_node="planner_node",
    )


def _build_reschedule_request_from_active_plan(
    *,
    user_id: str,
    active_plan_snapshot: dict[str, Any],
) -> PlannerRequest:
    """Build a real planner revise request from the live active plan snapshot."""

    if not active_plan_snapshot.get("has_plan") or not active_plan_snapshot.get("plan_details"):
        raise ValueError(f"No active plan found for user_id={user_id}")

    plan_details = active_plan_snapshot["plan_details"]
    intake_snapshot = plan_details.get("intake_snapshot") or {}
    intake = IntakeAgentOutput.model_validate(intake_snapshot)

    start_date = plan_details.get("start_date")
    end_date = plan_details.get("end_date")
    if not start_date or not end_date:
        days = plan_details.get("days") or []
        if not days:
            raise ValueError(f"Active plan has no date window for user_id={user_id}")
        start_date = days[0]["date"]
        end_date = days[-1]["date"]

    from src.tools.calendar_ops import get_non_skedioai_events_core

    calendar_raw = get_non_skedioai_events_core(start_date, end_date, user_id=user_id)
    calendar_blocks = json.loads(calendar_raw).get("blocked_slots", [])

    current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M")
    available_time_windows = _build_available_time_windows(
        start_date=start_date,
        end_date=end_date,
        time_blocks=intake.availability.time_blocks if intake.availability else {},
        calendar_blocks=calendar_blocks,
        deadline_datetime=intake.goal.deadline_datetime if intake.goal else None,
        current_datetime=current_datetime,
    )
    scheduling_context = _build_scheduling_context(
        intake=intake,
        calendar_blocks=calendar_blocks,
        available_time_windows=available_time_windows,
    )

    return PlannerRequest(
        user_id=user_id,
        intake=intake,
        scheduling_context=scheduling_context,
        active_plan_context=active_plan_snapshot,
    )


# ─────────────────────────────────────────────
# Background Processor
# ─────────────────────────────────────────────

async def process_calendar_change(channel_id: str, resource_id: str):
    """Fetch changed events, detect clashes, trigger reschedule."""
    try:
        user_id = _resolve_user_from_channel(channel_id)
        if not user_id:
            logger.warning("No user mapping for channel %s; ignoring webhook", channel_id)
            return

        # 1. Fetch active plan
        plan_result = get_active_plan_snapshot(user_id)
        if not plan_result.get("has_plan"):
            logger.info("No active plan — nothing to check")
            return

        active_plan = plan_result["plan_details"]
        active_plan_id = active_plan["plan_id"]

        days = active_plan.get("days", [])
        if not days:
            return

        start_date = days[0]["date"]
        end_date = days[-1]["date"]

        # 2. Get non-skedioai events using your existing MCP client
        calendar_client = get_calendar_client()
        result_json = await calendar_client.get_non_skedioai_events(
            start_date=start_date,
            end_date=end_date,
            user_id=user_id,
        )
        data = json.loads(result_json)
        blocked_slots = data.get("blocked_slots", [])

        # 3. Filter already-processed events
        new_events = []
        for e in blocked_slots:
            cache_key = f"{e['date']}_{e['start_time']}_{e['title']}"
            if cache_key not in _processed_events:
                new_events.append(e)
                _processed_events.add(cache_key)

        if not new_events:
            logger.info("No new non-SkedioAI events found")
            return

        # 4. Check each new event for clashes
        for event in new_events:
            clashes = detect_clash(event, active_plan)

            if not clashes:
                logger.info(f"No clash: {event.get('title', '')}")
                continue

            logger.info(f"🚨 Clash! '{event['title']}' hits {len(clashes)} session(s)")
            await trigger_auto_reschedule(clashes, event["title"], active_plan_id, user_id)

    except Exception as e:
        logger.exception("❌ process_calendar_change failed: %s", e)


# ─────────────────────────────────────────────
# Webhook Endpoint
# ─────────────────────────────────────────────

@webhook_router.post("/calendar/webhook")
async def calendar_webhook(request: Request, background_tasks: BackgroundTasks):
    """Google Calendar push notification endpoint."""
    resource_state = request.headers.get("X-Goog-Resource-State", "")
    channel_id = request.headers.get("X-Goog-Channel-ID", "")
    resource_id = request.headers.get("X-Goog-Resource-ID", "")

    logger.info(f"📅 Webhook: state={resource_state}")

    if resource_state not in ("exists", "update", "create"):
        return {"status": "ignored"}

    background_tasks.add_task(process_calendar_change, channel_id, resource_id)
    return {"status": "received"}


# ─────────────────────────────────────────────
# Register Webhook (run once)
# ─────────────────────────────────────────────

async def register_calendar_webhook(webhook_url: str, user_id: str):
    """
    Run once to register webhook with Google Calendar.

    Local dev steps:
        1. ngrok http 8000
        2. asyncio.run(register_calendar_webhook("https://xxxx.ngrok.io/calendar/webhook", user_id="..."))
    """
    import uuid
    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials

    TOKEN_PATH = "create_events.json"
    SCOPES = ["https://www.googleapis.com/auth/calendar"]

    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    service = build("calendar", "v3", credentials=creds)

    body = {
        "id": str(uuid.uuid4()),
        "type": "web_hook",
        "address": webhook_url,
        "expiration": str(int((datetime.now(timezone.utc).timestamp() + 604800) * 1000))  # 7 days
    }

    result = service.events().watch(calendarId="primary", body=body).execute()
    channel_id = result.get("id", "")
    _channel_user_map[channel_id] = user_id
    logger.info("✅ Webhook registered: channel=%s → user=%s", channel_id, user_id)
    return result
