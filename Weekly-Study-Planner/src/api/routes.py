"""
SkedioAI FastAPI Backend
======================
Endpoints for the React study plan checklist + Chat with Supervisor.
NOW USES MCP for calendar operations.

Run with:
    uvicorn src.api.routes:app --reload --port 8000
"""

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from src.api.auth import get_current_user

from src.api import calendar_oauth
from pydantic import BaseModel
from typing import Any, Dict, Optional, List
from datetime import date, datetime
from fastapi import Query
import json
import os
import logging
import time

logger = logging.getLogger(__name__)

from langchain_core.messages import HumanMessage, AIMessage
from langsmith import traceable

from src.tools.test_mcp_client import get_calendar_client
from src.services.active_plan import get_active_plan_rows, invalidate_active_plan_cache
from src.services.review_flow import scoped_thread_id
from src.services.user_memory import build_runtime_user_context

app = FastAPI(title="SkedioAI API", version="1.0.0")
perf_logger = logging.getLogger("skedioai.perf.http")

# Allow React dev server + production Vercel deployment
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "https://saathi-frontend-fplr.onrender.com",
    "https://saathi-backend-6m8q.onrender.com",
    "http://127.0.0.1:5173",
]

frontend_url = os.getenv("FRONTEND_URL")
if frontend_url:
    ALLOWED_ORIGINS.append(frontend_url.rstrip("/"))


class TimingMiddleware:
    """Pure ASGI middleware for request timing — avoids BaseHTTPMiddleware's
    cancel-scope bug that conflicts with MCP client's anyio task groups."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        started_at = time.perf_counter()
        path = scope.get("path", "")
        method = scope.get("method", "")

        status_code = None

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status")
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            perf_logger.exception(
                "stage=http_request method=%s path=%s status=500 duration_ms=%s",
                method,
                path,
                round((time.perf_counter() - started_at) * 1000, 2),
            )
            raise

        if path != "/health" and status_code is not None:
            perf_logger.info(
                "stage=http_request method=%s path=%s status=%s duration_ms=%s",
                method,
                path,
                status_code,
                round((time.perf_counter() - started_at) * 1000, 2),
            )


app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"https://.*\.(vercel\.app|onrender\.com)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TimingMiddleware)


@app.get("/health")
def health_check():
    from src.agents.supervisor_slop import ROUTER_PROMPT_VERSION

    return {
        "status": "ok",
        "service": "skedioai-api",
        "router_prompt_version": ROUTER_PROMPT_VERSION,
    }


@app.get("/email/status")
async def email_status(user_id: str = Depends(get_current_user)):
    """Report whether SMTP-backed alerts and webhook email delivery are configured."""
    from src.api.user_email import get_user_alert_email

    smtp_configured = bool(os.getenv("GMAIL_USER") and os.getenv("GMAIL_APP_PASSWORD"))
    webhook_enabled = os.getenv("ENABLE_CALENDAR_WEBHOOKS", "0") == "1"
    webhook_user_bound = bool(os.getenv("SAATHI_WEBHOOK_USER_ID"))
    webhook_fallback_email = bool(os.getenv("SAATHI_ALERT_EMAIL"))
    recipient = None
    lookup_error = None
    try:
        recipient = get_user_alert_email(user_id)
    except Exception as exc:
        lookup_error = str(exc)

    return {
        "auth_active": True,
        "recipient": recipient,
        "smtp_configured": smtp_configured,
        "ready": bool(recipient and smtp_configured),
        "delivery_mode": "profile_email" if recipient else ("fallback_email" if webhook_fallback_email else "unconfigured"),
        "webhook_enabled": webhook_enabled,
        "webhook_user_bound": webhook_user_bound,
        "webhook_fallback_email": webhook_fallback_email,
        "lookup_error": lookup_error,
    }


app.include_router(calendar_oauth.router)

if os.getenv("ENABLE_CALENDAR_WEBHOOKS", "0") == "1":
    try:
        from src.api.calendar_webhook import webhook_router

        app.include_router(webhook_router)
    except Exception as e:
        logger.warning("Calendar webhook router skipped: %s", e)


_checkpointer = None
_supervisor_graph = None


def get_supervisor_graph(checkpointer):
    """Get or create the current slop supervisor graph - cached for performance."""
    global _supervisor_graph
    if _supervisor_graph is None:
        from src.agents.supervisor_slop import create_supervisor_graph
        _supervisor_graph = create_supervisor_graph(checkpointer)
    return _supervisor_graph


calendar_client = get_calendar_client()


# ─────────────────────────────────────────────
# Startup/Shutdown Events
# ─────────────────────────────────────────────
from aiosqlite import connect


@app.on_event("startup")
async def startup_event():
    global _checkpointer
    # Create connection and saver manually
    conn = await connect("skedioai.db")
    _checkpointer = AsyncSqliteSaver(conn)
    await _checkpointer.setup()
    logger.info("FastAPI started with SQLite Checkpointer; Calendar MCP connects lazily")


@app.on_event("shutdown")
async def shutdown_event():
    global _checkpointer
    try:
        await calendar_client.disconnect()
    except Exception as e:
        logger.warning("Calendar MCP disconnect skipped: %s", e)
    if _checkpointer and _checkpointer.conn:
        await _checkpointer.conn.close()
    logger.info("FastAPI disconnected")


# ─────────────────────────────────────────────
# Request / Response Models
# ─────────────────────────────────────────────


class SessionCompleteRequest(BaseModel):
    session_id: str
    actual_hours: Optional[float] = None
    content_updates: Optional[List["SessionContentUpdate"]] = None


class SessionContentUpdate(BaseModel):
    content_match_key: str
    status: str = "done"
    time_spent: float = 0.0


class SessionSkipRequest(BaseModel):
    session_id: str


class TickSubtopicRequest(BaseModel):
    session_id: str
    content_match_key: str
    time_spent: Optional[float] = 0.0


class UntickSubtopicRequest(BaseModel):
    session_id: str
    content_match_key: str


class SessionUndoRequest(BaseModel):
    session_id: str


class ChatRequest(BaseModel):
    model_config = {"extra": "forbid"}
    message: str
    thread_id: Optional[str] = None
    ui_context: Optional[Dict[str, Any]] = None


class ChatActionRequest(BaseModel):
    model_config = {"extra": "forbid"}
    action: str
    thread_id: Optional[str] = None


class ChatActionOption(BaseModel):
    id: str
    label: str


class ChatResponse(BaseModel):
    thread_id: str
    reply: str
    phase: str
    plan_committed: bool
    actions: List[ChatActionOption] = []
    draft_plan: Optional[Dict[str, Any]] = None
    pending_ui: Optional[Dict[str, Any]] = None


class PlanUpdateRequest(BaseModel):
    model_config = {"extra": "forbid"}
    plan_name: Optional[str] = None


class LearnerMemoryUpsertRequest(BaseModel):
    model_config = {"extra": "forbid"}
    memory_id: Optional[str] = None
    kind: str
    text: str
    source: Optional[str] = "manual"


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def _get_db():
    from src.database.neo4j import Neo4jManager

    return Neo4jManager()


def _get_vs():
    from src.database.vector_store import VectorStore

    return VectorStore()


def _json_or_default(value: Any, default: Any):
    if value is None:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return default
    return value


def _scoped_thread_id(user_id: str, thread_id: Optional[str]) -> str:
    """Namespace conversation threads by authenticated user."""

    return scoped_thread_id(user_id, thread_id)


async def _delete_thread_checkpoints(thread_id: str) -> Dict[str, int]:
    """Delete persisted LangGraph checkpoint rows for one scoped thread."""

    if _checkpointer is None or getattr(_checkpointer, "conn", None) is None:
        raise HTTPException(status_code=503, detail="Checkpointer is not available")

    writes_cursor = await _checkpointer.conn.execute(
        "DELETE FROM writes WHERE thread_id = ?",
        (thread_id,),
    )
    checkpoints_cursor = await _checkpointer.conn.execute(
        "DELETE FROM checkpoints WHERE thread_id = ?",
        (thread_id,),
    )
    await _checkpointer.conn.commit()

    return {
        "writes_deleted": int(getattr(writes_cursor, "rowcount", 0) or 0),
        "checkpoints_deleted": int(getattr(checkpoints_cursor, "rowcount", 0) or 0),
    }


def _chat_response_from_result(result: dict, thread_id: str) -> ChatResponse:
    """Normalize supervisor graph output into the chat response contract."""

    ai_msg = result["messages"][-1] if result.get("messages") else None
    reply = result.get("final_reply") or (
        ai_msg.content if isinstance(ai_msg, AIMessage) else "..."
    )
    phase = (
        result.get("routing_decision").intent
        if result.get("routing_decision")
        else "chat"
    )
    worker_envelope = result.get("worker_envelope") or {}
    plan_committed = bool(
        result.get("committed")
        or (worker_envelope.get("data") or {}).get("committed")
    )
    verified_plan = result.get("verified_plan")
    pending_ui = result.get("pending_ui")
    has_pending_draft = bool(verified_plan) and not plan_committed

    actions: List[ChatActionOption] = []
    if has_pending_draft and pending_ui and pending_ui.get("type") == "plan_review":
        for action in pending_ui.get("actions") or []:
            action_id = str(action.get("id") or "").strip()
            label = str(action.get("label") or "").strip()
            if action_id and label:
                actions.append(ChatActionOption(id=action_id, label=label))

    return ChatResponse(
        thread_id=thread_id,
        reply=reply,
        phase=phase,
        plan_committed=plan_committed,
        actions=actions,
        draft_plan=verified_plan if has_pending_draft else None,
        pending_ui=pending_ui,
    )


async def _get_supervisor_state(thread_id: str) -> Dict[str, Any]:
    """Return the persisted supervisor state for one thread id."""

    app_graph = get_supervisor_graph(_checkpointer)
    snapshot = await app_graph.aget_state({"configurable": {"thread_id": thread_id}})
    values = getattr(snapshot, "values", None) or {}
    return values if isinstance(values, dict) else {}


def _pending_review_response_from_state(result: Dict[str, Any], thread_id: str) -> ChatResponse:
    """Return one chat response from persisted pending-review state."""

    if not result.get("verified_plan") or result.get("committed"):
        raise HTTPException(status_code=404, detail="No pending plan review found.")

    normalized = dict(result)
    normalized["pending_ui"] = normalized.get("pending_ui") or {
        "type": "plan_review",
        "actions": [
            {"id": "approve_plan", "label": "Approve plan"},
            {"id": "request_changes", "label": "Request changes"},
            {"id": "cancel_plan", "label": "Cancel plan"},
        ],
    }
    normalized["final_reply"] = (
        normalized.get("final_reply")
        or (normalized.get("worker_envelope") or {}).get("message")
        or "Your draft plan is ready for review."
    )
    normalized["routing_decision"] = normalized.get("routing_decision") or type(
        "Decision",
        (),
        {"intent": "planner"},
    )()
    return _chat_response_from_result(normalized, thread_id)


def _require_owned_session(neo, session_id: str, user_id: str) -> Dict[str, Any]:
    """Load a session and ensure it belongs to the authenticated user."""

    session = neo.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Session does not belong to this user")
    return session


async def _sync_calendar_session_status(
    session: Dict[str, Any],
    completed: bool,
    user_id: str,
) -> Dict[str, Any]:
    """Best-effort sync from Neo4j session truth to the matching SkedioAI calendar event."""
    if not session:
        return {"calendar_sync": "skipped", "reason": "missing session"}

    date_value = session.get("date")
    start_time = session.get("start_time")
    end_time = session.get("end_time")
    if not date_value or not start_time or not end_time:
        return {"calendar_sync": "skipped", "reason": "missing session slot"}

    try:
        result = await calendar_client.mark_event_completed(
            date=date_value,
            start_time=start_time,
            end_time=end_time,
            completed=completed,
            user_id=user_id,
        )
        return {"calendar_sync": result}
    except Exception as e:
        logger.warning("Calendar completion sync failed: %s", e)
        return {"calendar_sync": "failed", "error": str(e)}


def _session_outcome_event_type(outcome: str) -> str:
    normalized = (outcome or "").strip().lower()
    if normalized == "done":
        return "session_complete"
    if normalized == "partial":
        return "session_partial"
    if normalized == "skipped":
        return "session_skipped"
    if normalized == "undo":
        return "session_undo"
    if normalized == "subtopic_complete":
        return "subtopic_complete"
    if normalized == "subtopic_undo":
        return "subtopic_undo"
    return "session_progress"


async def _record_session_outcome_memory_event(
    *,
    user_id: str,
    session: Dict[str, Any],
    outcome: str,
    actual_hours: Optional[float] = None,
    content_match_key: Optional[str] = None,
) -> None:
    """Best-effort memory evidence after durable session progress changes."""

    try:
        event_type = _session_outcome_event_type(outcome)
        session_title = session.get("title") or session.get("session_title") or "Study session"
        subject = session.get("subject") or session.get("subjects") or ""
        when = " ".join(
            str(part)
            for part in [
                session.get("date"),
                session.get("start_time"),
                session.get("end_time"),
            ]
            if part
        )
        text_parts = [f"{session_title} marked {outcome}"]
        if subject:
            text_parts.append(f"subject={subject}")
        if when:
            text_parts.append(f"when={when}")
        if actual_hours is not None:
            text_parts.append(f"actual_hours={actual_hours}")
        if content_match_key:
            text_parts.append(f"content={content_match_key}")

        vs = _get_vs()
        logged = await vs.log_event(
            user_id=user_id,
            event_type=event_type,
            text="; ".join(text_parts),
            metadata={
                "session_id": session.get("session_id") or session.get("id"),
                "outcome": outcome,
                "subject": subject,
                "date": session.get("date"),
                "start_time": session.get("start_time"),
                "end_time": session.get("end_time"),
                "actual_hours": actual_hours,
                "content_match_key": content_match_key,
            },
        )
        if not logged:
            return

        from src.memory.triggers import schedule_session_outcome_memory_synthesis

        schedule_session_outcome_memory_synthesis(
            user_id=user_id,
            outcome=outcome,
        )
    except Exception as exc:
        logger.warning(
            "Session outcome memory event skipped user_id=%s session_id=%s outcome=%s error=%s",
            user_id,
            session.get("session_id") or session.get("id"),
            outcome,
            exc,
        )


def _content_name(content: Dict[str, Any]) -> str:
    return (
        content.get("canonical_name")
        or content.get("name")
        or content.get("match_key")
        or "Untitled content"
    )


def _group_plan_by_day(raw_plan: list) -> dict:
    if not raw_plan:
        return {}

    first = raw_plan[0]
    plan_id = first.get("plan_id")
    days_map: Dict[str, Dict[str, Any]] = {}
    seen_sessions = set()

    for row in raw_plan:
        day_date = row.get("date")
        if not day_date:
            continue

        if day_date not in days_map:
            days_map[day_date] = {
                "day_num": row.get("day_num"),
                "date": day_date,
                "capacity_hours": row.get("capacity_hours") or 0,
                "total_hours": row.get("day_total_hours") or 0,
                "sessions": [],
            }

        session_id = row.get("session_id")
        if not session_id or session_id in seen_sessions:
            continue
        seen_sessions.add(session_id)

        contents = []
        for content in row.get("contents") or []:
            content = dict(content)
            contents.append(
                {
                    "match_key": content.get("match_key"),
                    "name": _content_name(content),
                    "subjects": content.get("subjects") or [],
                    "chapters": content.get("chapters") or [],
                    "type": content.get("type") or "subtopic",
                    "status": content.get("status") or "pending",
                    "time_spent": content.get("time_spent") or 0,
                }
            )

        days_map[day_date]["sessions"].append(
            {
                "session_id": session_id,
                "title": row.get("session_title") or "Study Session",
                "session_type": row.get("session_type") or "chapter",
                "start_time": row.get("start_time"),
                "end_time": row.get("end_time"),
                "estimated_hours": row.get("estimated_hours") or 0,
                "allocated_hours": _json_or_default(row.get("allocated_hours"), []),
                "actual_time": row.get("actual_time") or 0,
                "status": row.get("session_status") or "pending",
                "contents": contents,
            }
        )

    for day in days_map.values():
        day["sessions"].sort(key=lambda s: s.get("start_time") or "")

    return {
        "plan_id": plan_id,
        "status": first.get("plan_status"),
        "total_hours": first.get("plan_total_hours") or 0,
        "risk_level": first.get("risk_level"),
        "intake_snapshot": _json_or_default(first.get("intake_snapshot"), {}),
        "days": sorted(days_map.values(), key=lambda d: d.get("day_num") or 0),
    }


def _chapter_key(subject: str, chapter: str) -> str:
    return f"{subject.strip().lower()}|{chapter.strip().lower()}"


def _allocation_targets_from_raw(raw_plan: list) -> Dict[str, Dict[str, Any]]:
    if not raw_plan:
        return {}

    raw_targets = _json_or_default(raw_plan[0].get("topic_time_estimates"), {})
    targets: Dict[str, Dict[str, Any]] = {}

    for key, hours in (raw_targets or {}).items():
        subject = ""
        chapter = str(key)
        if "|" in str(key):
            parts = str(key).split("|")
            subject = parts[0]
            chapter = parts[-1]
        targets[_chapter_key(subject, chapter)] = {
            "subject": subject,
            "chapter": chapter,
            "estimated_hours": float(hours or 0),
            "scheduled_hours": 0.0,
            "completed_hours": 0.0,
        }

    return targets


def _empty_progress_payload() -> Dict[str, Any]:
    return {"by_subject": {}}


def _empty_dashboard_stats_payload() -> Dict[str, Any]:
    return {
        "hours_studied": 0,
        "hours_remaining": 0,
        "hours_target": 0,
        "subtopics_done": 0,
        "total_subtopics": 0,
        "sessions_completed": 0,
        "total_sessions": 0,
        "daily_hours": [],
        "topic_breakdown": [],
    }


def _build_progress_from_grouped_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Build progress payload from grouped plan (Plan -> Day -> Session -> Content)."""
    by_subject: Dict[str, List[Dict[str, Any]]] = {}
    chapter_map: Dict[str, Dict[str, Any]] = {}

    for day in plan.get("days", []):
        for session in day.get("sessions", []):
            contents = session.get("contents") or []
            session_done = session.get("status") == "done"

            # Derive subjects and chapters from contents
            subjects_seen: set = set()
            chapters_seen: set = set()
            for c in contents:
                for s in c.get("subjects") or []:
                    subjects_seen.add(s)
                for ch in c.get("chapters") or []:
                    chapters_seen.add(ch)

            # Group by subject+chapter from content
            for subj in subjects_seen or {"Unknown"}:
                for ch in chapters_seen or {"Unknown"}:
                    key = f"{subj}|{ch}"
                    if key not in chapter_map:
                        chapter_map[key] = {
                            "subject": subj,
                            "task": ch,
                            "match_key": f"{subj}_{ch}",
                            "status": "pending",
                            "actual_hours": 0.0,
                            "estimated_hours": 0.0,
                            "subtopics": [],
                            "subtopics_completed": set(),
                        }

                    agg = chapter_map[key]

                    # Add contents belonging to this chapter
                    for c in contents:
                        c_chapters = c.get("chapters") or []
                        if ch not in c_chapters:
                            continue
                        agg["subtopics"].append({
                            "name": c.get("name") or c.get("match_key"),
                            "match_key": c.get("match_key"),
                            "time_spent": c.get("time_spent") or 0,
                        })
                        if c.get("status") == "done":
                            agg["subtopics_completed"].add(c.get("match_key"))
                            agg["actual_hours"] += c.get("time_spent") or 0

                    # Accumulate estimated hours from allocated_hours
                    for alloc in session.get("allocated_hours") or []:
                        if alloc.get("chapter") == ch:
                            agg["estimated_hours"] += alloc.get("hours") or 0

    for agg in chapter_map.values():
        subj = agg["subject"]
        if subj not in by_subject:
            by_subject[subj] = []

        agg["subtopics_completed"] = list(agg["subtopics_completed"])
        agg["percent"] = (
            round((agg["actual_hours"] / agg["estimated_hours"] * 100))
            if agg["estimated_hours"]
            else 0
        )
        if agg["actual_hours"] > 0:
            agg["status"] = (
                "in_progress" if agg["actual_hours"] < agg["estimated_hours"] else "done"
            )

        by_subject[subj].append(agg)

    return {"by_subject": by_subject}


def _build_dashboard_stats_from_raw(
    raw: List[Dict[str, Any]],
    user_id: str,
    neo,
) -> Dict[str, Any]:
    """Build dashboard stats from grouped plan (Plan -> Day -> Session -> Content)."""
    if not raw:
        return _empty_dashboard_stats_payload()

    plan = _group_plan_by_day(raw)
    days = plan.get("days", [])

    total_sessions = 0
    completed_sessions = 0
    total_hours = 0
    studied_hours = 0
    topic_hours: Dict[str, Dict[str, Any]] = {}
    daily_data = []

    for day in days:
        day_date = day.get("date", "")
        sessions = day.get("sessions", [])
        day_hours = 0

        for s in sessions:
            est = s.get("estimated_hours", 0) or 0
            total_sessions += 1
            total_hours += est
            day_hours += est

            # Sum actual hours from done contents
            session_actual = 0.0
            for c in s.get("contents") or []:
                if c.get("status") == "done":
                    session_actual += c.get("time_spent") or 0

            if s.get("status") == "done":
                completed_sessions += 1
                studied_hours += session_actual if session_actual > 0 else est

            title = s.get("title") or "Unknown"
            if title not in topic_hours:
                topic_hours[title] = {
                    "hours": 0,
                    "subject": title,
                }
            topic_hours[title]["hours"] += session_actual if session_actual > 0 else est

        if day_hours > 0:
            daily_data.append({"date": day_date, "hours": day_hours})

    counts = neo.get_subtopic_counts(user_id)
    total_subtopics = counts["total_subtopics"]
    subtopics_done = counts["subtopics_done"]

    topic_breakdown = [
        {"topic": k, "hours": v["hours"], "subject": v["subject"]}
        for k, v in topic_hours.items()
    ]

    return {
        "hours_studied": round(studied_hours, 2),
        "hours_remaining": round(total_hours - studied_hours, 2),
        "hours_target": round(total_hours, 2),
        "subtopics_done": subtopics_done,
        "total_subtopics": total_subtopics,
        "sessions_completed": completed_sessions,
        "total_sessions": total_sessions,
        "daily_hours": daily_data,
        "topic_breakdown": topic_breakdown,
    }


def _build_workspace_bootstrap(user_id: str) -> Dict[str, Any]:
    neo = _get_db()
    raw = get_active_plan_rows(user_id, neo)
    if not raw:
        return {
            "plan": None,
            "progress": _empty_progress_payload(),
            "stats": _empty_dashboard_stats_payload(),
        }

    plan = _group_plan_by_day(raw)
    return {
        "plan": plan,
        "progress": _build_progress_from_grouped_plan(plan),
        "stats": _build_dashboard_stats_from_raw(raw, user_id, neo),
    }


@app.get("/plan/week")
def get_week_plan(user_id: str = Depends(get_current_user)):
    """Full active plan grouped by day."""
    raw = get_active_plan_rows(user_id)
    if not raw:
        raise HTTPException(status_code=404, detail="No active plan found.")
    return _group_plan_by_day(raw)


@app.get("/plan/active")
def get_active_plan(user_id: str = Depends(get_current_user)):
    """Active plan: Plan -> Day -> Session -> Content."""
    raw = get_active_plan_rows(user_id)
    if not raw:
        raise HTTPException(status_code=404, detail="No active plan found.")
    return _group_plan_by_day(raw)


@app.get("/app/bootstrap")
def get_workspace_bootstrap(user_id: str = Depends(get_current_user)):
    """Single boot payload for the main app workspace."""
    return _build_workspace_bootstrap(user_id)


@app.get("/backlog/chapters")
def get_chapter_backlog(user_id: str = Depends(get_current_user)):
    """Chapter-level backlog derived from Neo4j session/content truth."""
    neo = _get_db()
    return {"chapters": neo.get_chapter_backlog(user_id)}


@app.get("/plan/allocation-summary")
def get_allocation_summary(user_id: str = Depends(get_current_user)):
    """Compare chapter targets against scheduled and completed session hours."""
    raw = get_active_plan_rows(user_id)
    if not raw:
        raise HTTPException(status_code=404, detail="No active plan found.")

    targets = _allocation_targets_from_raw(raw)
    plan = _group_plan_by_day(raw)

    for day in plan.get("days", []):
        for session in day.get("sessions", []):
            allocations = session.get("allocated_hours") or []
            if not allocations and session.get("contents"):
                first = session["contents"][0]
                subjects = first.get("subjects") or []
                chapters = first.get("chapters") or []
                allocations = [
                    {
                        "subject": subjects[0] if subjects else "",
                        "chapter": chapters[0] if chapters else "",
                        "hours": session.get("estimated_hours") or 0,
                    }
                ]

            for allocation in allocations:
                subject = allocation.get("subject") or ""
                chapter = allocation.get("chapter") or ""
                if not chapter:
                    continue

                exact_key = _chapter_key(subject, chapter)
                fallback_key = _chapter_key("", chapter)
                key = exact_key if exact_key in targets else fallback_key
                if key not in targets:
                    targets[key] = {
                        "subject": subject,
                        "chapter": chapter,
                        "estimated_hours": 0.0,
                        "scheduled_hours": 0.0,
                        "completed_hours": 0.0,
                    }

                hours = float(allocation.get("hours") or 0)
                targets[key]["scheduled_hours"] += hours

            for content in session.get("contents") or []:
                if content.get("status") != "done":
                    continue
                subjects = content.get("subjects") or [""]
                chapters = content.get("chapters") or []
                time_spent = float(content.get("time_spent") or 0)
                for chapter in chapters:
                    subject = subjects[0] if subjects else ""
                    exact_key = _chapter_key(subject, chapter)
                    fallback_key = _chapter_key("", chapter)
                    key = exact_key if exact_key in targets else fallback_key
                    if key not in targets:
                        targets[key] = {
                            "subject": subject,
                            "chapter": chapter,
                            "estimated_hours": 0.0,
                            "scheduled_hours": 0.0,
                            "completed_hours": 0.0,
                        }
                    targets[key]["completed_hours"] += time_spent

    summary = []
    for item in targets.values():
        target = item["estimated_hours"]
        scheduled = round(item["scheduled_hours"], 2)
        completed = round(item["completed_hours"], 2)
        if target and scheduled < target * 0.95:
            status = "under_planned"
        elif target and scheduled > target * 1.05:
            status = "over_planned"
        elif completed >= target and target:
            status = "completed"
        else:
            status = "on_track"

        summary.append(
            {
                "subject": item["subject"],
                "chapter": item["chapter"],
                "estimated_hours": round(target, 2),
                "scheduled_hours": scheduled,
                "completed_hours": completed,
                "remaining_hours": round(max(scheduled - completed, 0), 2),
                "status": status,
            }
        )

    summary.sort(key=lambda x: (x["subject"], x["chapter"]))
    return {"plan_id": plan.get("plan_id"), "allocations": summary}


@app.get("/plan/all")
def get_all_plans(user_id: str = Depends(get_current_user), offset: int = 0, limit: int = 20):
    """All plans for a user, paginated, sorted by date descending."""
    neo = _get_db()
    result = neo.list_plans_paginated(user_id, offset=offset, limit=limit)
    return result


@app.get("/plan/today")
def get_today_sessions(user_id: str = Depends(get_current_user)):
    """Today's sessions only."""
    raw = get_active_plan_rows(user_id)
    if not raw:
        raise HTTPException(status_code=404, detail="No active plan found.")

    plan = _group_plan_by_day(raw)
    today = date.today().strftime("%Y-%m-%d")

    today_day = next((d for d in plan["days"] if d["date"] == today), None)
    if not today_day:
        return {
            "plan_id": plan["plan_id"],
            "date": today,
            "sessions": [],
            "message": "No sessions today.",
        }

    done = sum(1 for s in today_day["sessions"] if s.get("status") == "done")
    total = len(today_day["sessions"])

    return {
        "plan_id": plan["plan_id"],
        "date": today,
        "summary": f"{done}/{total} sessions done",
        **today_day,
    }


@app.get("/plan/progress")
def get_progress(user_id: str = Depends(get_current_user)):
    """Task-level progress (hours completed vs total) for all tasks."""
    raw = get_active_plan_rows(user_id)
    if not raw:
        raise HTTPException(status_code=404, detail="No active plan found.")

    return _build_progress_from_grouped_plan(_group_plan_by_day(raw))


@app.get("/stats/dashboard")
def get_dashboard_stats(user_id: str = Depends(get_current_user)):
    """Dashboard stats for investor view - hours, progress, exam countdown."""
    neo = _get_db()
    raw = get_active_plan_rows(user_id, neo)
    return _build_dashboard_stats_from_raw(raw, user_id, neo)


@app.get("/stats/graph")
def get_knowledge_graph(user_id: str = Depends(get_current_user)):
    """
    Build an Obsidian-style knowledge graph traversing:
    User → Subject → Chapter → Content (subtopic)
    
    Content nodes have c.subjects (list) and c.chapters (list).
    A subtopic can belong to multiple chapters (and chapters to multiple subjects).
    We track completion status from the Session-[TARGETS_CONTENT]->Content relationship.
    """
    neo = _get_db()

    # Fetch all Content the user has ever encountered via Sessions
    query = """
    MATCH (u:User {id: $user_id})-[:PERFORMED]->(s:Session)-[r:TARGETS_CONTENT]->(c:Content)
    WITH c,
         collect(DISTINCT r.status) AS statuses,
         count(DISTINCT s.session_id) AS session_count
    RETURN
        c.match_key          AS match_key,
        c.canonical_name     AS name,
        c.subjects           AS subjects,
        c.chapters           AS chapters,
        // Mark as done if ANY relationship is done
        CASE WHEN 'done' IN statuses THEN 'done' ELSE 'pending' END AS status,
        session_count
    """

    rows = neo.graph.query(query, {"user_id": user_id})

    nodes_dict = {}
    links_set  = set()   # (source_id, target_id) to dedupe
    links      = []

    def add_node(node_id, name, group, **extra):
        if node_id not in nodes_dict:
            nodes_dict[node_id] = {"id": node_id, "name": name, "group": group, **extra}

    def add_link(source, target):
        key = (source, target)
        if key not in links_set:
            links_set.add(key)
            links.append({"source": source, "target": target})

    # User node (the center of the universe)
    user_node_id = f"user_{user_id}"
    add_node(user_node_id, "You", "user")

    for row in rows:
        match_key    = row.get("match_key") or ""
        name         = row.get("name")      or match_key
        subjects     = row.get("subjects")  or []
        chapters     = row.get("chapters")  or []
        status       = row.get("status")    or "pending"
        sessions     = row.get("session_count") or 0

        if isinstance(subjects, str): subjects = [subjects]
        if isinstance(chapters, str): chapters = [chapters]

        subjects = [s for s in subjects if s]
        chapters = [c for c in chapters if c]

        # Fallback if lists are empty
        if not subjects:  subjects = ["General"]
        if not chapters:  chapters = ["General"]

        # ── Subject nodes (linked from User) ──
        for subj in subjects:
            subj_id = f"subj_{subj}"
            add_node(subj_id, subj, "subject", subject=subj)
            add_link(user_node_id, subj_id)

            # ── Chapter nodes (linked from Subject) ──
            for chap in chapters:
                chap_id = f"chap_{subj}_{chap}"
                add_node(chap_id, chap, "chapter", subject=subj)
                add_link(subj_id, chap_id)

                # ── Subtopic / Content node ──
                sub_id = f"sub_{match_key}"
                add_node(
                    sub_id, name, "subtopic",
                    status=status,
                    subject=subj,
                    sessions=sessions,
                )
                add_link(chap_id, sub_id)

    return {
        "nodes": list(nodes_dict.values()),
        "links": links,
    }



@app.post("/session/complete")
async def complete_session(
    req: SessionCompleteRequest, user_id: str = Depends(get_current_user)
):
    """
    Mark session complete using session_id.
    """
    neo = _get_db()

    session = _require_owned_session(neo, req.session_id, user_id)

    estimated_hours = session.get("estimated_hours", 0)
    session_status = "done"
    if req.content_updates:
        updates = [item.model_dump() for item in req.content_updates]
        session_result = neo.update_session_content_times(req.session_id, updates)
        actual_hours = session_result.get("actual_time", 0)
        session_status = session_result.get("status", "pending")
    else:
        actual_hours = req.actual_hours if req.actual_hours else estimated_hours
        neo.complete_session(req.session_id, actual_hours)

    from src.services.backlog_sync import sync_chapter_backlog

    try:
        await sync_chapter_backlog(user_id, neo)
    except Exception as e:
        logger.warning("Failed to sync backlog: %s", e)

    calendar_result = await _sync_calendar_session_status(
        session,
        completed=(session_status == "done"),
        user_id=user_id,
    )
    invalidate_active_plan_cache(user_id)
    await _record_session_outcome_memory_event(
        user_id=user_id,
        session=session,
        outcome=session_status,
        actual_hours=actual_hours,
    )

    return {
        "status": "success",
        "session_id": req.session_id,
        "actual_hours": actual_hours,
        "estimated_hours": estimated_hours,
        "content_updates_applied": bool(req.content_updates),
        **calendar_result,
    }


from datetime import timedelta


@app.post("/session/undo")
async def undo_session(
    req: SessionUndoRequest, user_id: str = Depends(get_current_user)
):
    """
    Undo completed session using session_id.
    Resets session back to pending (keeps session, resets content statuses).
    """
    neo = _get_db()

    session = _require_owned_session(neo, req.session_id, user_id)

    neo.reset_session(req.session_id)
    calendar_result = await _sync_calendar_session_status(
        session,
        completed=False,
        user_id=user_id,
    )

    from src.services.backlog_sync import sync_chapter_backlog

    try:
        await sync_chapter_backlog(user_id, neo)
    except Exception as e:
        logger.warning("Failed to sync backlog: %s", e)
    invalidate_active_plan_cache(user_id)
    await _record_session_outcome_memory_event(
        user_id=user_id,
        session=session,
        outcome="undo",
    )

    return {
        "status": "success",
        "session_id": req.session_id,
        "message": "Session undone and backlog updated",
        **calendar_result,
    }


@app.post("/session/untick")
async def untick_subtopic(
    req: UntickSubtopicRequest, user_id: str = Depends(get_current_user)
):
    """Remove content completion status using session_id."""
    neo = _get_db()

    session = _require_owned_session(neo, req.session_id, user_id)

    neo.untick_content(req.session_id, req.content_match_key)
    calendar_result = await _sync_calendar_session_status(
        session,
        completed=False,
        user_id=user_id,
    )

    from src.services.backlog_sync import sync_chapter_backlog

    try:
        await sync_chapter_backlog(user_id, neo)
    except Exception as e:
        logger.warning("Failed to sync backlog: %s", e)
    invalidate_active_plan_cache(user_id)
    await _record_session_outcome_memory_event(
        user_id=user_id,
        session=session,
        outcome="subtopic_undo",
        content_match_key=req.content_match_key,
    )

    session_with_contents = neo.get_session_with_contents(req.session_id)
    completed_contents = []
    if session_with_contents and session_with_contents.get("contents"):
        completed_contents = [
            c.get("canonical_name", c.get("match_key"))
            for c in session_with_contents["contents"]
            if c.get("status") == "done"
        ]

    return {
        "status": "success",
        "session_id": req.session_id,
        "content_match_key": req.content_match_key,
        "subtopics_completed": completed_contents,
        **calendar_result,
    }

@app.post("/session/tick-subtopic")
async def tick_subtopic(
    req: TickSubtopicRequest, user_id: str = Depends(get_current_user)
):
    """Mark content as complete using session_id."""
    neo = _get_db()

    session = _require_owned_session(neo, req.session_id, user_id)

    neo.tick_content(req.session_id, req.content_match_key, time_spent=req.time_spent)


    from src.services.backlog_sync import sync_chapter_backlog

    try:
        await sync_chapter_backlog(user_id, neo)
    except Exception as e:
        logger.warning("Failed to sync backlog: %s", e)
    invalidate_active_plan_cache(user_id)

    session_with_contents = neo.get_session_with_contents(req.session_id)
    completed_contents = []
    session_done = False
    if session_with_contents and session_with_contents.get("contents"):
        completed_contents = [
            c.get("canonical_name", c.get("match_key"))
            for c in session_with_contents["contents"]
            if c.get("status") == "done"  # Fixed from rel_status to status
        ]
        session_done = session_with_contents.get("status") == "done"

    calendar_result = await _sync_calendar_session_status(
        session,
        completed=session_done,
        user_id=user_id,
    )
    await _record_session_outcome_memory_event(
        user_id=user_id,
        session=session,
        outcome="done" if session_done else "subtopic_complete",
        actual_hours=req.time_spent,
        content_match_key=req.content_match_key,
    )

    return {
        "status": "success",
        "session_id": req.session_id,
        "content_match_key": req.content_match_key,
        "subtopics_completed": completed_contents,
        **calendar_result,
    }





@app.delete("/plan/delete")
async def delete_active_plan(user_id: str = Depends(get_current_user)):
    """Delete active plan and all calendar events via MCP"""
    neo = _get_db()

    # Mark plan as DELETED
    query = """
    MATCH (u:User {id: $user_id})-[:HAS_PLAN]->(p:Plan {status: 'ACTIVE'})
    SET p.status = 'DELETED', p.actual_end_date = date()
    RETURN p.plan_id
    """
    result = neo.graph.query(query, {"user_id": user_id})

    if not result:
        raise HTTPException(404, "No active plan")
    invalidate_active_plan_cache(user_id)

    vs = _get_vs()
    await vs.log_event(
        user_id=user_id,
        event_type="plan_delete",
        text=f"Plan Deleted: {result[0]['p.plan_id']}",
        metadata={"plan_id": result[0]["p.plan_id"]},
    )

    # ✨ DELETE ALL SKEDIOAI EVENTS VIA MCP
    try:
        today = date.today()
        from datetime import timedelta
        delete_result = await calendar_client.delete_skedioai_events_in_range(
            time_min_iso=(today - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00+05:30"),
            time_max_iso=(today + timedelta(days=90)).strftime("%Y-%m-%dT23:59:59+05:30"),
            user_id=user_id,
        )
        logger.info("Calendar delete all result: %s", delete_result)
    except Exception as e:
        logger.warning("Calendar delete all failed: %s", e)

    return {"status": "deleted", "plan_id": result[0]["p.plan_id"]}


@app.get("/calendar/events/external")
async def get_external_calendar_events(
    start_date: str = Query(...),
    end_date: str = Query(...),
    user_id: str = Depends(get_current_user)
):
    """Fetch non-SkedioAI events from Google Calendar via MCP"""
    try:
        import json
        result_str = await calendar_client.get_non_skedioai_events(
            start_date=start_date,
            end_date=end_date,
            user_id=user_id,
        )
        events = json.loads(result_str)
        if isinstance(events, dict) and events.get("error"):
            raise HTTPException(status_code=424, detail=events["error"])
        return {"events": events}
    except HTTPException:
        raise
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=502, detail=f"Calendar MCP returned invalid JSON: {e}")
    except Exception as e:
        logger.error("Failed to fetch external events: %s", e)
        raise HTTPException(status_code=424, detail=str(e))


# ─────────────────────────────────────────────
# Chat Routes (Supervisor Slop Agent)
# ─────────────────────────────────────────────

async def _invoke_supervisor_chat(
    *,
    message: Optional[str],
    thread_id: str,
    user_id: str,
    ui_context: Optional[Dict[str, Any]] = None,
    ui_action: Optional[Dict[str, Any]] = None,
) -> ChatResponse:
    """Invoke Supervisor for one chat/action turn and normalize the response."""

    @traceable(
        run_type="chain",
        name="skedioai_chat",
        metadata={"thread_id": thread_id, "session_id": thread_id},
    )
    async def _run_graph(inputs: dict):
        app_graph = get_supervisor_graph(_checkpointer)
        config = {"configurable": {"thread_id": thread_id}}
        return await app_graph.ainvoke(inputs, config=config)

    result = await _run_graph(
        {
            "messages": [HumanMessage(content=message)] if message else [],
            "user_id": user_id,
            "user_context": await build_runtime_user_context(
                user_id=user_id,
                query=message or "",
            ),
            "ui_context": ui_context,
            "ui_action": ui_action,
        }
    )

    return _chat_response_from_result(result, thread_id)


async def _stream_supervisor_chat(
    *,
    message: Optional[str],
    thread_id: str,
    user_id: str,
    ui_context: Optional[Dict[str, Any]] = None,
    ui_action: Optional[Dict[str, Any]] = None,
):
    """Stream user-facing supervisor output as NDJSON."""

    @traceable(
        run_type="chain",
        name="skedioai_chat_stream",
        metadata={"thread_id": thread_id, "session_id": thread_id},
    )
    async def _run_graph_stream(inputs: dict):
        app_graph = get_supervisor_graph(_checkpointer)
        config = {"configurable": {"thread_id": thread_id}}
        async for mode, data in app_graph.astream(
            inputs,
            config=config,
            stream_mode=["custom", "values"],
        ):
            yield mode, data

    async def event_generator():
        stream_started_at = time.perf_counter()
        first_graph_event_ms = None
        first_chunk_ms = None
        event_count = 0
        chunk_count = 0
        final_result = None
        try:
            async for mode, data in _run_graph_stream(
                {
                    "messages": [HumanMessage(content=message)] if message else [],
                    "user_id": user_id,
                    "user_context": await build_runtime_user_context(
                        user_id=user_id,
                        query=message or "",
                    ),
                    "ui_context": ui_context,
                    "ui_action": ui_action,
                }
            ):
                event_count += 1
                if first_graph_event_ms is None:
                    first_graph_event_ms = round(
                        (time.perf_counter() - stream_started_at) * 1000, 2
                    )
                    perf_logger.info(
                        "stage=chat_stream_first_graph_event thread_id=%s user_id=%s first_graph_event_ms=%s mode=%s",
                        thread_id,
                        user_id,
                        first_graph_event_ms,
                        mode,
                    )
                if mode == "custom":
                    if not isinstance(data, dict):
                        continue
                    if data.get("event") != "user_facing_chunk":
                        continue
                    text = str(data.get("text") or "")
                    if not text:
                        continue
                    chunk_count += 1
                    if first_chunk_ms is None:
                        first_chunk_ms = round(
                            (time.perf_counter() - stream_started_at) * 1000, 2
                        )
                        perf_logger.info(
                            "stage=chat_stream_first_chunk thread_id=%s user_id=%s first_chunk_ms=%s",
                            thread_id,
                            user_id,
                            first_chunk_ms,
                        )
                    yield json.dumps({"type": "chunk", "text": text}) + "\n"
                    continue

                if mode == "values":
                    final_result = data

            if final_result is None:
                raise RuntimeError("Supervisor graph returned no final state.")

            final_response = _chat_response_from_result(final_result, thread_id)
            perf_logger.info(
                "stage=chat_stream_done thread_id=%s user_id=%s total_ms=%s first_graph_event_ms=%s first_chunk_ms=%s event_count=%s chunk_count=%s",
                thread_id,
                user_id,
                round((time.perf_counter() - stream_started_at) * 1000, 2),
                first_graph_event_ms,
                first_chunk_ms,
                event_count,
                chunk_count,
            )
            yield json.dumps(
                {
                    "type": "done",
                    "thread_id": final_response.thread_id,
                    "reply": final_response.reply,
                    "phase": final_response.phase,
                    "plan_committed": final_response.plan_committed,
                    "actions": [action.model_dump() for action in final_response.actions],
                    "draft_plan": final_response.draft_plan,
                    "pending_ui": final_response.pending_ui,
                }
            ) + "\n"

        except Exception as exc:
            perf_logger.warning(
                "stage=chat_stream_error thread_id=%s user_id=%s total_ms=%s first_graph_event_ms=%s first_chunk_ms=%s event_count=%s chunk_count=%s error=%s",
                thread_id,
                user_id,
                round((time.perf_counter() - stream_started_at) * 1000, 2),
                first_graph_event_ms,
                first_chunk_ms,
                event_count,
                chunk_count,
                str(exc),
            )
            yield json.dumps({"type": "error", "detail": str(exc)}) + "\n"

    return StreamingResponse(
        event_generator(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/chat/send", response_model=ChatResponse)
async def send_message(req: ChatRequest, user_id: str = Depends(get_current_user)):
    """Send message to SkedioAI supervisor"""
    try:
        thread_id = _scoped_thread_id(user_id, req.thread_id)
        response = await _invoke_supervisor_chat(
            thread_id=thread_id,
            user_id=user_id,
            message=req.message,
            ui_context=req.ui_context,
            ui_action=None,
        )
        from src.memory.triggers import schedule_chat_memory_review

        schedule_chat_memory_review(user_id=user_id, message=req.message)
        return response

    except Exception as e:
        logger.exception("send_message failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/send/stream")
async def send_message_stream(req: ChatRequest, user_id: str = Depends(get_current_user)):
    """Stream one chat turn from the supervisor."""
    try:
        thread_id = _scoped_thread_id(user_id, req.thread_id)
        response = await _stream_supervisor_chat(
            thread_id=thread_id,
            user_id=user_id,
            message=req.message,
            ui_context=req.ui_context,
            ui_action=None,
        )
        from src.memory.triggers import schedule_chat_memory_review

        schedule_chat_memory_review(user_id=user_id, message=req.message)
        return response
    except Exception as e:
        logger.exception("send_message_stream failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/chat/pending-review", response_model=ChatResponse)
async def get_pending_review(
    thread_id: str = Query("planner-review"),
    user_id: str = Depends(get_current_user),
):
    """Return the current pending planner review for one authenticated thread."""

    try:
        scoped_thread_id = _scoped_thread_id(user_id, thread_id)
        state = await _get_supervisor_state(scoped_thread_id)
        return _pending_review_response_from_state(state, scoped_thread_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("get_pending_review failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/action", response_model=ChatResponse)
async def chat_action(req: ChatActionRequest, user_id: str = Depends(get_current_user)):
    """Handle UI approval/rejection actions against the active Supervisor thread."""
    try:
        thread_id = _scoped_thread_id(user_id, req.thread_id)
        return await _invoke_supervisor_chat(
            thread_id=thread_id,
            user_id=user_id,
            message=None,
            ui_context=None,
            ui_action={"id": req.action},
        )
    except Exception as e:
        logger.exception("chat_action failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/chat/reset/{thread_id}")
async def reset_conversation(thread_id: str, user_id: str = Depends(get_current_user)):
    """Clear persisted conversation history for one authenticated user's thread."""

    scoped_thread_id = _scoped_thread_id(user_id, thread_id)
    deleted = await _delete_thread_checkpoints(scoped_thread_id)
    return {
        "status": "reset",
        "thread_id": scoped_thread_id,
        "message": "Conversation history cleared from checkpointer",
        **deleted,
    }


@app.get("/memory/learner")
async def get_learner_memory(user_id: str = Depends(get_current_user)):
    """Return the current learner-memory records for this user."""

    vs = _get_vs()
    items = await vs.list_learner_memory(user_id)
    return {"items": items, "count": len(items)}


@app.put("/memory/learner")
async def upsert_learner_memory(
    req: LearnerMemoryUpsertRequest,
    user_id: str = Depends(get_current_user),
):
    """Create or overwrite one learner-memory record."""

    kind = str(req.kind or "").strip()
    text = str(req.text or "").strip()
    source = str(req.source or "manual").strip() or "manual"
    if not kind:
        raise HTTPException(status_code=400, detail="kind is required")
    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    normalized_kind = kind.lower().replace(" ", "_")
    stable_key = str(req.memory_id or f"{user_id}:{normalized_kind}").strip()
    vs = _get_vs()
    ok = await vs.upsert_memory(
        user_id=user_id,
        kind=normalized_kind,
        source=source,
        text=text,
        stable_key=stable_key,
    )
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to store learner memory")

    return {
        "ok": True,
        "item": {
            "memory_id": stable_key,
            "user_id": user_id,
            "kind": normalized_kind,
            "source": source,
            "text": text,
        },
    }


@app.delete("/memory/learner/{memory_id}")
async def delete_learner_memory(
    memory_id: str,
    user_id: str = Depends(get_current_user),
):
    """Delete one learner-memory record owned by this user."""

    vs = _get_vs()
    items = await vs.list_learner_memory(user_id)
    if not any(str(item.get("memory_id") or "") == memory_id for item in items):
        raise HTTPException(status_code=404, detail="Learner memory not found")

    ok = await vs.delete_memory(memory_id=memory_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to delete learner memory")

    return {"ok": True, "memory_id": memory_id}


@app.post("/plan/mark-inactive")
async def mark_plan_inactive(user_id: str = Depends(get_current_user)):
    """Mark active plan as inactive → triggers lobby deportation"""
    neo = _get_db()
    query = """
    MATCH (u:User {id: $user_id})-[:HAS_PLAN]->(p:Plan {status: 'ACTIVE'})
    SET p.status = 'INACTIVE', p.archived_at = datetime()
    RETURN p.plan_id AS plan_id
    """
    result = neo.graph.query(query, {"user_id": user_id})
    if not result:
        raise HTTPException(404, "No active plan found")
    invalidate_active_plan_cache(user_id)
    return {"status": "inactive", "plan_id": result[0]["plan_id"]}


@app.get("/plan/{plan_id}")
def get_plan_by_id(plan_id: str, user_id: str = Depends(get_current_user)):
    """Fetch any plan by ID for read-only view"""
    neo = _get_db()
    raw = neo.get_plan_by_id(user_id, plan_id)  # add this to neo4j_client
    if not raw:
        raise HTTPException(404, "Plan not found")
    return _group_plan_by_day(raw)


@app.post("/session/skip")
async def skip_session(
    req: SessionSkipRequest, user_id: str = Depends(get_current_user)
):
    """
    Mark session as SKIPPED using session_id.
    """
    neo = _get_db()

    session = _require_owned_session(neo, req.session_id, user_id)

    neo.mark_session_skipped(req.session_id)

    from src.services.backlog_sync import sync_chapter_backlog

    try:
        await sync_chapter_backlog(user_id, neo)
    except Exception as e:
        logger.warning("Failed to sync backlog: %s", e)
    invalidate_active_plan_cache(user_id)

    calendar_result = await _sync_calendar_session_status(
        session,
        completed=False,
        user_id=user_id,
    )
    await _record_session_outcome_memory_event(
        user_id=user_id,
        session=session,
        outcome="skipped",
    )

    return {
        "status": "success",
        "session_id": req.session_id,
        "message": "Session marked as skipped",
        **calendar_result,
    }


# ─────────────────────────────────────────────
# Plan Memory Endpoints
# ─────────────────────────────────────────────


@app.get("/plans")
def get_plans(
    user_id: str = Depends(get_current_user), offset: int = 0, limit: int = 5
):
    """
    List all plans for a user with pagination.

    Args:
        user_id: User ID (defaults to current user)
        offset: How many plans to skip (default 0)
        limit: How many plans to return (default 5)

    Returns:
        List of plans with details
    """
    neo = _get_db()
    result = neo.list_plans_paginated(user_id=user_id, offset=offset, limit=limit)
    return result


@app.get("/plans/search")
def search_plans_by_date(
    user_id: str = Depends(get_current_user),
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
):
    """
    Search for plans within a date range.

    Args:
        user_id: User ID (defaults to current user)
        start_date: Start of date range (YYYY-MM-DD)
        end_date: End of date range (YYYY-MM-DD)

    Returns:
        List of matching plans
    """
    neo = _get_db()
    plans = neo.search_plans_by_date(
        user_id=user_id, start_date=start_date, end_date=end_date
    )
    return {"plans": plans, "count": len(plans)}


@app.patch("/plans/{plan_id}")
def update_plan(
    plan_id: str,
    updates: PlanUpdateRequest,
    user_id: str = Depends(get_current_user),
):
    """
    Update allowed plan metadata.

    Args:
        plan_id: Plan ID to update
        user_id: User ID (defaults to current user)
        updates: Allowed metadata fields to update

    Returns:
        Success status
    """
    neo = _get_db()
    payload = updates.model_dump(exclude_none=True)

    if not payload:
        raise HTTPException(status_code=400, detail="No updates provided")

    if set(payload.keys()) - {"plan_name"}:
        raise HTTPException(status_code=400, detail="Unsupported plan update fields")

    if "plan_name" in payload:
        success = neo.update_plan_name(
            user_id=user_id, plan_id=plan_id, new_name=payload["plan_name"]
        )
    else:
        raise HTTPException(status_code=400, detail="Unsupported plan update fields")

    if success:
        invalidate_active_plan_cache(user_id)
        return {"status": "success", "message": "Plan updated"}
    raise HTTPException(status_code=404, detail="Plan not found or update failed")


# ─────────────────────────────────────────────
# Email / SMTP Test
# ─────────────────────────────────────────────

class EmailTestRequest(BaseModel):
    recipient: str


@app.post("/email/test")
def email_test(body: EmailTestRequest):
    """Send a smoke-test email via Gmail SMTP. Returns success or error."""
    import smtplib
    from email.mime.text import MIMEText

    gmail_user = os.getenv("GMAIL_USER")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD")

    if not gmail_user or not gmail_password:
        raise HTTPException(
            status_code=500,
            detail="GMAIL_USER and GMAIL_APP_PASSWORD env vars are not set",
        )

    msg = MIMEText("SkedioAI SMTP test — if you received this, email is working.")
    msg["Subject"] = "SkedioAI SMTP Test"
    msg["From"] = gmail_user
    msg["To"] = body.recipient

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_password)
            server.sendmail(gmail_user, body.recipient, msg.as_string())
        logger.info("📧 Test email sent to %s", body.recipient)
        return {"status": "ok", "sent_to": body.recipient}
    except Exception as exc:
        logger.error("❌ SMTP test failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"SMTP error: {exc}")
