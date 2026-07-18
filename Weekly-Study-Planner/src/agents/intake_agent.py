"""LangGraph Intake agent for building and validating study-planning contracts.

This file owns contract formation, not schedule generation.

Mental model:
- Intake talks to the user, asks follow-ups, and gathers evidence.
- The model can suggest a contract, but `commit_intake` is the only place where
  that contract becomes accepted state.
- Deterministic validation enriches the accepted contract with feasibility,
  calendar blocks, and planner-ready scheduling context.

State glossary:
- `intake.status = pending`: still collecting or repairing contract facts
- `intake.status = approved`: contract is ready for planner
- `intake.status = rejected`: intake could not accept the request as-is
"""

import os
import logging
import json
import time
import asyncio
import traceback
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, TypedDict, Annotated
from dotenv import load_dotenv
from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    SystemMessage,
    ToolMessage,
    BaseMessage,
)
from src.services.intake_contract_validator import (
    validate_intake_contract,
)
from src.prompts.intake.prompt import intake_agent_prompt
from langchain_core.tools import tool
from langgraph.graph.message import add_messages
from langsmith import traceable
from langgraph.graph import StateGraph, START, END
from src.models.intake import IntakeAgentOutput


# ── Structured metrics tracking ────────────────────────────────────────────────
class IntakeMetrics:
    """Track intake agent performance metrics."""
    
    def __init__(self):
        """Initialize counters used for lightweight runtime telemetry."""

        self.total_sessions = 0
        self.completed_sessions = 0
        self.failed_sessions = 0
        self.tool_calls = {}
        self.avg_turns = 0
        self.turn_counts = []
        self.errors = []
    
    def record_session_start(self):
        """Record that a new Intake session has started."""

        self.total_sessions += 1
    
    def record_session_complete(self, turns: int):
        """Record that an Intake session completed and store its turn count."""

        self.completed_sessions += 1
        self.turn_counts.append(turns)
        self.avg_turns = sum(self.turn_counts) / len(self.turn_counts)
    
    def record_session_failure(self, error: str):
        """Record a session-level failure for later diagnostics."""

        self.failed_sessions += 1
        self.errors.append({"error": error, "timestamp": datetime.now().isoformat()})
    
    def record_tool_call(self, tool_name: str, success: bool, duration_ms: float):
        """Record one tool execution result and its duration."""

        if tool_name not in self.tool_calls:
            self.tool_calls[tool_name] = {"calls": 0, "successes": 0, "failures": 0, "total_ms": 0}
        self.tool_calls[tool_name]["calls"] += 1
        if success:
            self.tool_calls[tool_name]["successes"] += 1
        else:
            self.tool_calls[tool_name]["failures"] += 1
        self.tool_calls[tool_name]["total_ms"] += duration_ms
    
    def get_summary(self) -> dict:
        """Return an aggregate snapshot of Intake runtime metrics."""

        return {
            "total_sessions": self.total_sessions,
            "completed_sessions": self.completed_sessions,
            "failed_sessions": self.failed_sessions,
            "success_rate": self.completed_sessions / max(1, self.total_sessions),
            "avg_turns": self.avg_turns,
            "tool_calls": self.tool_calls,
            "recent_errors": self.errors[-5:] if self.errors else []
        }

_intake_metrics = IntakeMetrics()


INTAKE_DEBUG = os.getenv("INTAKE_DEBUG", "0").lower() in {"1", "true", "yes", "on"}


def intake_debug_print(*args, **kwargs) -> None:
    """Print debug output only when INTAKE_DEBUG is enabled."""

    if INTAKE_DEBUG:
        print(*args, **kwargs)


@tool
@traceable(run_type="tool", name="get_active_plan")
def get_active_plan(user_id: str) -> dict:
    """
    Get the user's current active plan with all days and sessions (V2).
    Returns sessions with session_id for API identification.
    """
    from src.database.neo4j import Neo4jManager

    try:
        neo4j = Neo4jManager()
        rows = neo4j.get_active_plan_sessions(user_id)

        if not rows:
            return {"has_plan": False, "message": "No active plan found"}

        first = rows[0]
        days_map = {}

        for row in rows:
            day_num = row["day_num"]
            if day_num not in days_map:
                days_map[day_num] = {
                    "day_num": day_num,
                    "date": row["date"],
                    "total_hours": row["day_total_hours"],
                    "sessions": [],
                    "capacity_hours": row["capacity_hours"],
                }

            if row["session_id"]:
                existing_ids = [s["session_id"] for s in days_map[day_num]["sessions"]]
                if row["session_id"] not in existing_ids:
                    session_contents = row.get("contents") or []
                    days_map[day_num]["sessions"].append(
                        {
                            "session_id": row["session_id"],
                            "title": row["session_title"],
                            "session_type": row["session_type"],
                            "estimated_hours": row["estimated_hours"],
                            "actual_time": row["actual_time"],
                            "start_time": row["start_time"],
                            "end_time": row["end_time"],
                            "status": row["session_status"],
                            "contents": session_contents,
                        }
                    )

        raw_snapshot = first.get("intake_snapshot", [])
        intake_snapshot = (
            json.loads(raw_snapshot)
            if isinstance(raw_snapshot, str)
            else (raw_snapshot or [])
        )

        return {
            "has_plan": True,
            "plan_details": {
                "plan_id": first["plan_id"],
                "risk_level": first.get("risk_level"),
                "total_hours": first["plan_total_hours"],
                "days": sorted(days_map.values(), key=lambda x: x["day_num"]),
                "intake_snapshot": intake_snapshot,
            },
        }

    except Exception as e:
        return {"has_plan": False, "error": str(e), "message": f"Failed: {str(e)}"}




load_dotenv()
logger = logging.getLogger(__name__)
intake_validator_logger = logging.getLogger("src.agents.intake_agent.validation")
logging.getLogger("httpx").setLevel(logging.WARNING)


def elapsed_ms(started_at: float) -> float:
    """Return elapsed milliseconds since a perf_counter timestamp."""

    return round((time.perf_counter() - started_at) * 1000, 2)


def _is_transient_connection_error(exc: Exception) -> bool:
    """Return True for short-lived API/DNS connection failures worth retrying."""

    text = repr(exc).lower()
    return any(
        marker in text
        for marker in (
            "apiconnectionerror",
            "connecterror",
            "connection error",
            "temporary failure in name resolution",
            "no address associated with hostname",
        )
    )


async def _ainvoke_with_connection_retries(
    runnable: Any,
    messages: list[BaseMessage],
    *,
    logger: logging.Logger,
    label: str,
    attempts: int = 3,
):
    """Invoke an LLM runnable, retrying only transient connection failures."""

    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await runnable.ainvoke(messages)
        except Exception as exc:
            last_exc = exc
            if attempt >= attempts or not _is_transient_connection_error(exc):
                raise
            delay = 0.75 * attempt
            logger.warning(
                "[%s] transient LLM connection failure attempt=%s/%s retry_in=%.2fs error=%r",
                label,
                attempt,
                attempts,
                delay,
                exc,
            )
            await asyncio.sleep(delay)

    raise last_exc  # type: ignore[misc]

os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGSMITH_TRACING"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "skedioai-intake-dev"


def serialize_tool_result_content(result: Any) -> str:
    """Serialize arbitrary tool output into message-safe string content."""

    if isinstance(result, str):
        return result
    return json.dumps(result, ensure_ascii=False, default=str)


def intake_is_ready_for_handoff(intake: Optional[IntakeAgentOutput]) -> bool:
    """Return true when the Intake contract is ready for planner handoff."""

    return bool(intake and intake.status == "approved")


def tool_result_succeeded(result: Any) -> bool:
    """Return false when a tool result explicitly carries an error state."""

    if isinstance(result, dict):
        if result.get("success") is False:
            return False
        return not bool(result.get("error"))

    content = serialize_tool_result_content(result)
    try:
        parsed = json.loads(content)
    except (TypeError, ValueError):
        return "error" not in content.lower()

    if isinstance(parsed, dict):
        if parsed.get("success") is False:
            return False
        return not bool(parsed.get("error"))

    return "error" not in content.lower()


@traceable(run_type="tool", name="sanitize_commit_payload")
def sanitize_commit_payload(payload: Any) -> dict:
    """Remove wrapper junk and repair harmless LLM shape slips before validation."""

    if not isinstance(payload, dict):
        return {}

    payload = dict(payload)

    # If the whole tool args object came through, unwrap it.
    if "intake_data" in payload and isinstance(payload["intake_data"], dict):
        payload = dict(payload["intake_data"])

    # Remove accidental LangChain/model wrapper fields.
    payload.pop("config", None)
    payload.pop("kwargs", None)
    payload.pop("metadata", None)

    # Top-level list fields should not be null.
    if payload.get("study_items") is None:
        payload["study_items"] = []

    # Repair common nested nulls.
    goal = payload.get("goal")
    if isinstance(goal, dict):
        goal = dict(goal)
        if goal.get("subjects") is None:
            goal["subjects"] = []
        if goal.get("study_scope") is None:
            goal["study_scope"] = []
        payload["goal"] = goal

    availability = payload.get("availability")
    if isinstance(availability, dict):
        availability = dict(availability)

        availability.pop("config", None)
        availability.pop("kwargs", None)
        availability.pop("metadata", None)

        if availability.get("daily_study_hours") is None:
            availability["daily_study_hours"] = {}

        if availability.get("time_blocks") is None:
            availability["time_blocks"] = {}

        if availability.get("planning_notes") is None:
            availability["planning_notes"] = []

        # Repair common mistake: study_items placed inside availability.
        if "study_items" in availability:
            misplaced = availability.pop("study_items")
            if payload.get("study_items") in (None, []):
                payload["study_items"] = misplaced or []

        # Remove non-schema junk.
        availability.pop("next", None)

        payload["availability"] = availability

    return payload


def _is_tool_argument_validation_error(exc: Exception) -> bool:
    """Return true for deterministic tool-argument validation failures."""

    exc_name = exc.__class__.__name__.lower()
    exc_text = str(exc).lower()
    return "validation" in exc_name or "validation error" in exc_text

class IntakeState(TypedDict):
    """Runtime state for the Intake worker graph.

    Important split:
    - `messages` carries the visible conversation/tool loop for this worker
    - `intake` is the current best contract snapshot
    - `scheduling_context` / `feasibility_result` are deterministic enrichments
    """

    messages: Annotated[list[BaseMessage], add_messages]
    user_id: str
    intake: Optional[IntakeAgentOutput]
    user_context: str
    calendar_blocks: Optional[list]
    active_plan_context: Optional[Dict[str, Any]]
    scheduling_context: Optional[Dict[str, Any]]
    feasibility_result: Optional[Dict[str, Any]]
    turn_count: int
    executed_tool_signatures: Optional[List[str]]


@tool
@traceable(run_type="tool", name="query_backlog")
async def query_backlog(user_id: str, topic: str | None = None) -> str:
    """Search the student's study progress and backlog.

This is the authoritative source for student progress: what is done, weak,
pending, estimated before, completed at subtopic level, and still remaining.

Use this after the academic scope is known enough to personalize effort,
priorities, remaining_subtopics, or to avoid asking the student what the system
may already know. Do not wait for the student to explicitly ask for a progress
lookup.

Args:
    user_id: Student namespace.
    topic: Optional semantic query, preferably subject + chapter/topic.
        Broad queries are useful when the student wants help choosing scope or
        asks for weak/pending areas across a subject.

Returns:
    JSON with matching backlog records. Records may include chapter, status,
    mastery, estimated hours, completed subtopics, and remaining subtopics.

If no records are found, continue honestly with student/context facts and mark
workload estimates as rough rather than pretending progress was grounded.
"""

    from src.database.vector_store import VectorStore

    vector_store = VectorStore()

    if not vector_store:
        return json.dumps({"found": False, "message": "No database connected"})

    try:
        if topic:
            results = await vector_store.search_backlog(
                user_id=user_id or "anonymous", query=topic, top_k=15
            )
        else:
            results = await vector_store.get_all_backlog(user_id=user_id or "anonymous")

        if not results:
            return json.dumps(
                {
                    "found": False,
                    "message": "No backlog entries found."
                    if not topic
                    else f"No backlog entries found for {topic}.",
                    "backlogs": [],
                }
            )

        backlog_info = []

        for r in results:
            match_key = r.get("match_key", "UNDEFINED")

            subtopics = r.get("subtopics", []) or []
            subtopics_completed = r.get("subtopics_completed", []) or []
            subtopics_remaining = r.get("subtopics_remaining", []) or []

            backlog_info.append(
                {
                    "id": r.get("id") or r.get("_id"),
                    "subject": match_key.split("|")[0]
                    if "|" in match_key
                    else r.get("subject"),
                    "chapter": match_key.split("|")[1]
                    if "|" in match_key
                    else r.get("chapter"),
                    "task": match_key,
                    "match_key": match_key,
                    "status": r.get("status", "UNDEFINED"),
                    "reason": r.get("reason", "UNDEFINED"),
                    "difficulty_signal": r.get("difficulty_signal", "UNDEFINED"),
                    "mastery_level": r.get("mastery_level", "UNDEFINED"),
                    "study_mode": r.get("study_mode", "UNDEFINED"),
                    "hours_estimated": r.get("hours_estimated", 0),
                    "hours_actual": r.get("hours_actual", 0),
                    "last_studied": r.get("last_studied"),
                    "updated_at": r.get("updated_at"),
                    # IMPORTANT: parent + subtopic-level truth
                    "subtopics": subtopics,
                    "subtopics_completed": subtopics_completed,
                    "subtopics_remaining": subtopics_remaining,
                    "subtopics_pending": subtopics_remaining,
                }
            )
        return json.dumps(
            {
                "found": True,
                "count": len(backlog_info),
                "backlogs": backlog_info,
            },
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"found": False, "error": str(e), "backlogs": []})


@tool
@traceable(run_type="tool", name="commit_intake")
def commit_intake(intake_data: IntakeAgentOutput) -> str:
    """Validate and save the latest intake contract checkpoint.

    Always pass the full latest `IntakeAgentOutput`, not only changed fields.

    Use:
    - `status="pending"` for normal progress, repair, and final-summary turns
    - `status="approved"` only after the student clearly confirms the final summary
    - `status="rejected"` only when the request truly cannot become a valid contract

    Call this after reading any evidence tools, not in the same batch.

    Returns validator feedback such as `ok`, `code`, `reason`, and feasibility details.

    If repair feedback is returned, keep the contract pending, fix the specific
    problem, and do not restart intake from scratch.
    """
    
    return "Intake response committed."

@tool
@traceable(run_type="tool", name="get_calendar_availability")
def get_calendar_availability(
    start_date: str,
    end_date: str,
    user_id: str | None = None,
) -> str:
    """Retrieve registered calendar commitments for a given date range.
    
    This retrieves commitments the user registered in Google Calendar for the
    requested period.
    
    Important: Calendar data is incomplete context. It captures only what the
    user has explicitly registered, not hidden life constraints (e.g., routines,
    untracked obligations). User-spoken commitments and rest windows are
    separate contract blockers. The final no-study constraints are the union of
    registered calendar events and user-stated commitments/rest.

    If calendar is unavailable or not connected, continue from user-stated
    blockers and say calendar was not checked when that affects confidence.
    
    Args:
        start_date: Inclusive start date in YYYY-MM-DD format.
        end_date: Inclusive end date in YYYY-MM-DD format.
        user_id: Optional student namespace.
    
    Returns:
        JSON with visible busy blocks and already completed SkedioAI tasks.
    """
    try:
        from src.tools.calendar_ops import get_non_skedioai_events_core

        raw_result = get_non_skedioai_events_core(start_date, end_date, user_id=user_id)

        data = json.loads(raw_result)
        all_slots = data.get("blocked_slots", [])

        completed_tasks = []
        actual_busy_time = []

        for slot in all_slots:
            title = slot.get("title", "")
            if "✅" in title or "\\u2705" in title:
                completed_tasks.append(slot)
            else:
                actual_busy_time.append(slot)

        return json.dumps(
            {
                "INTERNAL_USE_ONLY": "Never show this to user.",
                "ALREADY_COMPLETED_TASKS_DO_NOT_RESCHEDULE": completed_tasks,
                "UNAVAILABLE_BUSY_TIME": actual_busy_time,
            },
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"error": str(e), "has_blocks": False, "blocked_slots": []})


ACADEMIC_YEAR = "2025-26"


@tool
@traceable(run_type="tool", name="query_syllabus")
async def query_syllabus(subject: str, chapter: str | None = None) -> str:
    """Search official CBSE Class 10th syllabus records.
    
    This is the authoritative source for the 2026 CBSE Class 10 curriculum.
    Use it to determine which chapters and topics are included or removed,
    along with their respective weightage.

    Use this when course truth can affect chapter naming, active/removed topics,
    topic size, or workload estimates. Once the student names a subject/chapter,
    prefer syllabus grounding before making firm study_items or hour estimates.
    If the lookup returns nothing, continue honestly and label any estimate as
    rough rather than presenting it as syllabus-grounded.
    
    Args:
        subject: Subject name or alias.
        chapter: Optional focused chapter/topic query.
    
    Returns:
        JSON with matching syllabus chapters and their metadata.
    """
    from src.database.vector_store import VectorStore

    if not subject or not subject.strip():
        return json.dumps({"found": False, "error": "Subject is required"})

    vs = VectorStore()
    subject = subject.strip()

    try:
        def norm(value: str | None) -> str:
            return " ".join(str(value or "").lower().replace("_", " ").split())

        subject_aliases = {
            "maths": "maths",
            "math": "maths",
            "mathematics": "maths",
            "science": "science",
            "sciences": "science",
            "english": "english",
            "eng": "english",
            "sst": "social_science",
            "social": "social_science",
            "social science": "social_science",
            "social_science": "social_science",
        }
        canonical_subject = subject_aliases.get(norm(subject), norm(subject))

        # Prefer metadata lookup. It avoids Gemini embeddings, which can timeout
        # and should not be required for basic subject/chapter truth.
        results = await vs.list_syllabus_by_subject(canonical_subject, top_k=50)

        if chapter and results:
            chapter_query = norm(chapter)
            chapter_tokens = set(chapter_query.split())

            def chapter_score(row: dict) -> int:
                haystack = norm(
                    " ".join(
                        [
                            str(row.get("chapter_name") or ""),
                            str(row.get("topic_key") or ""),
                            str(row.get("active_topics") or ""),
                            str(row.get("removed_topics") or ""),
                        ]
                    )
                )
                if chapter_query and chapter_query in haystack:
                    return 100
                return len(chapter_tokens.intersection(haystack.split()))

            scored = [(chapter_score(r), r) for r in results]
            exact_matches = [r for score, r in scored if score >= 100]
            if exact_matches:
                results = exact_matches
            else:
                minimum_score = 1 if len(chapter_tokens) <= 1 else 2
                results = [r for score, r in scored if score >= minimum_score]
            results.sort(
                key=lambda r: chapter_score(r),
                reverse=True,
            )

        if not results and chapter:
            # Last resort for fuzzy phrases only. If this times out, the tool
            # still returns an honest miss instead of blocking whole-subject use.
            results = await vs.search_syllabus(f"{canonical_subject} {chapter}", top_k=5)

        # Filter out random matches from other subjects
        results = [
            r
            for r in results
            if norm(r.get("subject")) == norm(canonical_subject)
        ]

        if not results:
            return json.dumps(
                {
                    "found": False,
                    "message": f"No chapters found for {subject} {chapter or ''}".strip(),
                }
            )

        chapters = []
        for r in results:
            chapters.append(
                {
                    "topic_key": r.get("topic_key"),
                    "chapter_name": r.get("chapter_name"),
                    "chapter_number": r.get("chapter_number"),
                    "chapter_status": r.get("chapter_status"),
                    "chapter_weightage_marks": r.get("chapter_weightage_marks"),
                    "active_topics": r.get("active_topics", []),
                    "removed_topics": r.get("removed_topics", []),
                }
            )

        return json.dumps({"found": True, "chapters": chapters})

    except Exception as e:
        return json.dumps({"found": False, "error": str(e)})


@tool
@traceable(run_type="tool", name="verify_claim_search")
def verify_claim_search(subject: str, chapter: str, user_claim: str) -> str:
    """Search the web to verify a syllabus dispute.

    Use only when syllabus truth is meaningfully disputed and outside evidence is
    needed before considering a syllabus update.

    This tool is read-only. It does not update the database.
    """
    import os
    import requests

    try:
        query = f"CBSE Class 10 {subject} {chapter} {ACADEMIC_YEAR} official syllabus"
        tavily_key = os.getenv("TAVILY_API_KEY")

        if not tavily_key:
            return json.dumps({"error": "Tavily API key not found"})

        res = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": tavily_key,
                "query": query,
                "search_depth": "advanced",
                "max_results": 5,
            },
            timeout=15,
        )

        if res.status_code != 200:
            return json.dumps(
                {"confirmed": False, "error": f"Tavily returned {res.status_code}"}
            )

        results = res.json().get("results", [])

        search_results = [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", "")[:300],
            }
            for r in results
        ]

        return json.dumps(
            {
                "query": query,
                "search_results": search_results,
                "recommendation": "requires_llm_review",
                "message": f"Found {len(results)} web results - review and decide whether to update",
                # Match user schema
                "academic_year": "2025-26",
                "subject": subject,
                "chapter_name": chapter,
                "chapter_status": "pending_verification",
            }
        )

    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
@traceable(run_type="tool", name="update_syllabus_entry")
async def update_syllabus_entry(
    subject: str,
    chapter: str,
    chapter_status: str,
    active_topics: List[str] = None,
    removed_topics: List[str] = None,
    chapter_weightage_marks: int = None,
    chapter_number: int = None,
    academic_year: str = "2025-26",
    subject_total_marks: int = None,
) -> str:
    """Update one syllabus entry in the database.

    Use only after strong verification that stored syllabus truth is wrong or
    outdated. Do not use during normal intake planning.

    Returns JSON with success status and the updated syllabus fields.
    """
    from src.database.vector_store import VectorStore
    from datetime import datetime, timezone

    vs = VectorStore()
    topic_key = f"{subject}|{chapter}"

    try:
        existing = await vs.search_syllabus(topic_key, top_k=1)
        existing_meta = existing[0] if existing else {}

        now = datetime.now(timezone.utc).isoformat()

        metadata = {
            "topic_key": topic_key,
            "subject": subject.lower(),
            "chapter_name": chapter,
            "chapter_number": chapter_number
            if chapter_number is not None
            else existing_meta.get("chapter_number"),
            "chapter_status": chapter_status,
            "academic_year": academic_year,
            "active_topics": active_topics
            if active_topics is not None
            else existing_meta.get("active_topics", []),
            "removed_topics": removed_topics
            if removed_topics is not None
            else existing_meta.get("removed_topics", []),
            "chapter_weightage_marks": chapter_weightage_marks
            if chapter_weightage_marks is not None
            else existing_meta.get("chapter_weightage_marks", 0),
            "subject_total_marks": subject_total_marks
            if subject_total_marks is not None
            else existing_meta.get("subject_total_marks", 80),
            "last_updated": now,
            "updated_at": now,
            "status": "user_corrected",
        }

        content = metadata.get("search_text") or (
            f"CBSE Class 10 {subject} {chapter}. "
            f"Status: {chapter_status}. "
            f"Active: {metadata['active_topics']}. "
            f"Removed: {metadata['removed_topics']}."
        )

        ok = await vs.upsert_syllabus(
            topic_key=topic_key, content=content, metadata=metadata
        )

        # Return matches user schema
        return json.dumps(
            {
                "success": ok,
                "message": f"Updated {chapter} → {chapter_status}",
                "topic_key": topic_key,
                "subject": metadata["subject"],
                "chapter_name": chapter,
                "chapter_status": chapter_status,
                "academic_year": metadata["academic_year"],
                "chapter_number": metadata.get("chapter_number"),
                "active_topics": metadata["active_topics"],
                "removed_topics": metadata["removed_topics"],
                "chapter_weightage_marks": metadata["chapter_weightage_marks"],
                "subject_total_marks": metadata.get("subject_total_marks"),
                "last_updated": metadata["last_updated"],
                "updated_at": metadata["updated_at"],
                "status": metadata["status"],
            }
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


intake_tools = [
    query_backlog,
    get_calendar_availability,
    query_syllabus,
    verify_claim_search,
    update_syllabus_entry,
    commit_intake,
]

class IntakeAgent:
    """Build and run the LangGraph Intake workflow.

    The compiled graph is a small agent/tools loop:
    - `agent` decides what evidence or contract update is needed
    - `tools` execute evidence lookups and the commit gate
    - loop until the contract is ready or the turn naturally ends
    """

    def __init__(self, llm_client: Any, vector_store: Optional[Any] = None):
        """Create one state-driven Intake agent and tool binding."""

        self.llm = llm_client
        self.llm_with_tools = llm_client.bind_tools(
            intake_tools,
            tool_choice="auto",
        )
        self.vector_store = vector_store

    def intake_agent(self):
        """Compile the Intake LangGraph with agent and tool-execution nodes."""

        tools_by_name = {tool.name: tool for tool in intake_tools}

        def build_intake_system_prompt(state: IntakeState) -> str:
            """Build the one canonical Intake system prompt."""

            return intake_agent_prompt(
                user_id=state.get("user_id", "anonymous"),
                current_intake=state.get("intake"),
                user_context=state.get("user_context", ""),
                date_time=datetime.now().strftime("%Y-%m-%d %H:%M | %A"),
            )

        def build_intake_messages(
            *,
            state: IntakeState,
            system_prompt: str,
            active_plan: Any,
        ) -> List[BaseMessage]:
            """Build the single Intake message path from state truth."""

            messages: List[BaseMessage] = [SystemMessage(content=system_prompt), *state["messages"]]
            if not (isinstance(active_plan, dict) and active_plan.get("has_plan")):
                return messages

            messages.append(
                SystemMessage(
                    content=(
                        "Active plan context for this user:\n"
                        f"{serialize_tool_result_content(active_plan)}"
                    )
                )
            )

            return messages

        def build_agent_invocation(state: IntakeState):
            """Build one Intake invocation from runtime truth."""

            prompt_started_at = time.perf_counter()
            active_plan = state.get("active_plan_context") or {
                "has_plan": False,
                "plan_details": None,
            }
            has_active_plan = bool(
                isinstance(active_plan, dict) and active_plan.get("has_plan")
            )
            system_prompt = build_intake_system_prompt(state)
            messages = build_intake_messages(
                state=state,
                system_prompt=system_prompt,
                active_plan=active_plan,
            )

            logger.info(
                "[PERF][INTAKE] prompt_build duration_ms=%s message_count=%s has_active_plan=%s",
                elapsed_ms(prompt_started_at),
                len(messages),
                has_active_plan,
            )

            return active_plan, has_active_plan, messages

        @traceable(run_type="chain", name="intake_call_agent")
        async def call_agent(state: IntakeState):
            """Invoke the single bound Intake LLM from runtime state.

            At least one tool call is structurally required. Evidence calls can
            loop back before commit_intake checkpoints the contract.
            """

            node_started_at = time.perf_counter()
            if state.get("messages") and isinstance(state["messages"][-1], HumanMessage):
                state["executed_tool_signatures"] = []
            active_plan, has_active_plan, messages = build_agent_invocation(state)

            llm_started_at = time.perf_counter()
            response = await _ainvoke_with_connection_retries(
                self.llm_with_tools,
                messages,
                logger=logger,
                label="INTAKE_LLM",
            )
            tool_names = [
                tc.get("name")
                for tc in getattr(response, "tool_calls", []) or []
            ]
            logger.info(
                "[PERF][INTAKE] llm has_active_plan=%s duration_ms=%s tool_calls=%s",
                has_active_plan,
                elapsed_ms(llm_started_at),
                tool_names,
            )
            logger.info(
                "[PERF][INTAKE] agent_node has_active_plan=%s duration_ms=%s",
                has_active_plan,
                elapsed_ms(node_started_at),
            )

            return {
                "messages": [response],
                "active_plan_context": active_plan,
                "executed_tool_signatures": state.get("executed_tool_signatures", []),
            }

        @traceable(run_type="chain", name="intake_call_tools")
        async def call_tools(state: IntakeState):
            """Execute requested tools and route commit_intake through validation.

            Ordinary evidence tools can run in parallel. `commit_intake` is
            special: it is the single authoritative gate that validates and
            writes intake state for this worker turn.
            """

            tools_node_started_at = time.perf_counter()
            last_message = state["messages"][-1]
            tool_messages = []
            executed_signatures = list(state.get("executed_tool_signatures") or [])

            # Track tools for this turn (no hard limit - multi-subject is valid)
            tool_calls = last_message.tool_calls or []

            # Increment turn counter
            state["turn_count"] = state.get("turn_count", 0) + 1

            intake_debug_print("\n🔧 Tools being called this turn:")
            for tc in tool_calls:
                intake_debug_print(f"   → {tc['name']}")
            intake_debug_print()

            logger.info(
                "[PERF][INTAKE] tools_node start tool_calls=%s",
                [tc.get("name") for tc in tool_calls],
            )

            async def execute_regular_tool(tool_call: dict) -> ToolMessage:
                """Execute a non-commit tool with retry and normalized ToolMessage output."""

                tool_name = tool_call["name"]
                tool_args = dict(tool_call["args"])
                if tool_name == "get_calendar_availability" and "user_id" not in tool_args:
                    tool_args["user_id"] = state.get("user_id")

                tool_obj = tools_by_name.get(tool_name)
                tool_signature = json.dumps(
                    {"name": tool_name, "args": tool_args},
                    ensure_ascii=False,
                    sort_keys=True,
                    default=str,
                )

                if tool_signature in executed_signatures:
                    logger.info(
                        "[INTAKE] duplicate_regular_tool_skipped name=%s args=%s",
                        tool_name,
                        tool_args,
                    )
                    return ToolMessage(
                        content=json.dumps(
                            {
                                "skipped": True,
                                "reason": "duplicate_regular_tool_same_turn",
                                "tool": tool_name,
                            },
                            ensure_ascii=False,
                        ),
                        name=tool_name,
                        tool_call_id=tool_call["id"],
                    )

                start_time = time.time()
                try:
                    if tool_obj is None:
                        result = json.dumps({"error": f"Tool not found: {tool_name}"})
                    else:
                        max_retries = 5
                        for attempt in range(max_retries + 1):
                            try:
                                result = await tool_obj.ainvoke(tool_args)
                                break
                            except Exception as e:
                                if _is_tool_argument_validation_error(e):
                                    logger.warning(
                                        f"[INTAKE] Tool {tool_name} schema validation failed: {e}"
                                    )
                                    result = json.dumps(
                                        {
                                            "error": f"Tool {tool_name} failed schema validation: {str(e)}",
                                            "retries": attempt,
                                            "tool": tool_name,
                                        }
                                    )
                                    break
                                if attempt < max_retries:
                                    logger.warning(
                                        f"[INTAKE] Tool {tool_name} failed (attempt {attempt + 1}): {e}"
                                    )
                                    await asyncio.sleep(0.5 * (attempt + 1))
                                else:
                                    logger.error(
                                        f"[INTAKE] Tool {tool_name} failed after {max_retries + 1} attempts: {e}"
                                    )
                                    result = json.dumps(
                                        {
                                            "error": f"Tool {tool_name} failed: {str(e)}",
                                            "retries": max_retries,
                                            "tool": tool_name,
                                        }
                                    )
                except Exception as e:
                    result = json.dumps({"error": str(e), "tool": tool_name})
                    _intake_metrics.record_session_failure(str(e))

                duration_ms = (time.time() - start_time) * 1000
                result_content = serialize_tool_result_content(result)
                success = tool_result_succeeded(result)
                _intake_metrics.record_tool_call(tool_name, success, duration_ms)
                logger.info(
                    "[PERF][INTAKE] tool name=%s duration_ms=%s success=%s",
                    tool_name,
                    round(duration_ms, 2),
                    success,
                )
                executed_signatures.append(tool_signature)

                return ToolMessage(
                    content=result_content,
                    name=tool_name,
                    tool_call_id=tool_call["id"],
                )

            if not any(tc["name"] == "commit_intake" for tc in tool_calls):
                # Normal evidence tools can run in parallel because they do not mutate state.
                intake_validator_logger.info(
                    "[VALIDATOR] dispatch path=regular tools=%s",
                    [tc["name"] for tc in tool_calls],
                )
                tool_messages = await asyncio.gather(
                    *(execute_regular_tool(tc) for tc in tool_calls)
                )
                logger.info(
                    "[PERF][INTAKE] tools_node end duration_ms=%s returned_messages=%s",
                    elapsed_ms(tools_node_started_at),
                    len(tool_messages),
                )
                return {
                    "messages": list(tool_messages),
                    "executed_tool_signatures": executed_signatures,
                }

            intake_validator_logger.info(
                "[VALIDATOR] dispatch path=commit tools=%s",
                [tc["name"] for tc in tool_calls],
            )

            mixed_commit_batch = any(
                tc["name"] == "commit_intake" for tc in tool_calls
            ) and any(tc["name"] != "commit_intake" for tc in tool_calls)
            if mixed_commit_batch:
                # Commit is deferred when evidence tools are in the same batch.
                # This keeps the LLM from validating a contract before reading evidence.
                regular_tool_messages = await asyncio.gather(
                    *(
                        execute_regular_tool(tc)
                        for tc in tool_calls
                        if tc["name"] != "commit_intake"
                    )
                )
                deferred_commit_messages = [
                    ToolMessage(
                        content=json.dumps(
                            {
                                "accepted": False,
                                "error": "commit_deferred_until_evidence_loaded",
                                "code": "commit_deferred_until_evidence_loaded",
                                "student_safe_summary": (
                                    "Evidence tools were requested in the same batch. "
                                    "Read their results, then call commit_intake again."
                                ),
                            },
                            ensure_ascii=False,
                        ),
                        name="commit_intake",
                        tool_call_id=tc["id"],
                    )
                    for tc in tool_calls
                    if tc["name"] == "commit_intake"
                ]
                return {
                    "messages": list(regular_tool_messages)
                    + deferred_commit_messages,
                    "executed_tool_signatures": executed_signatures,
                }

            for tool_call in tool_calls:
                tool_name = tool_call["name"]
                tool_args = dict(tool_call["args"])
                if tool_name == "get_calendar_availability" and "user_id" not in tool_args:
                    tool_args["user_id"] = state.get("user_id")

                if tool_name == "commit_intake":
                    # commit_intake is the only path allowed to mutate the intake
                    # contract and its planner-facing scheduling context.
                    commit_started_at = time.perf_counter()
                    intake_payload = sanitize_commit_payload(tool_args)

                    validation = validate_intake_contract(
                        intake_payload=intake_payload,
                        user_id=state.get("user_id"),
                        runtime_state=state,
                        logger=intake_validator_logger,
                    )
                    clean_intake_data = validation.intake
                    intake_is_ready = intake_is_ready_for_handoff(clean_intake_data)
                    output_message = (
                        clean_intake_data.message
                        if clean_intake_data
                        else validation.student_safe_summary
                    )

                    commit_duration_ms = elapsed_ms(commit_started_at)
                    _intake_metrics.record_tool_call(
                        "commit_intake",
                        validation.accepted,
                        commit_duration_ms,
                    )

                    logger.info(
                        "[PERF][INTAKE] tool name=commit_intake duration_ms=%s success=%s intake_ready=%s code=%s",
                        commit_duration_ms,
                        validation.accepted,
                        intake_is_ready,
                        validation.code,
                    )

                    intake_validator_logger.info(
                        "[VALIDATOR] commit_intake status=%s intake_ready=%s turn=%s accepted=%s code=%s",
                        clean_intake_data.status if clean_intake_data else None,
                        intake_is_ready,
                        state.get("turn_count"),
                        validation.accepted,
                        validation.code,
                    )

                    if validation.accepted and intake_is_ready:
                        _intake_metrics.record_session_complete(state.get("turn_count", 0))

                    logger.info(
                        "[PERF][INTAKE] tools_node end duration_ms=%s returned_delta=true",
                        elapsed_ms(tools_node_started_at),
                    )

                    tool_msg = ToolMessage(
                        content=json.dumps(
                            validation.tool_payload(),
                            ensure_ascii=False,
                            default=str,
                        ),
                        name="commit_intake",
                        tool_call_id=tool_call["id"],
                    )

                    if not validation.accepted:
                        # Do not promote failed draft into current accepted intake.
                        # Keep last accepted/pending checkpoint as current_intake.
                        next_intake = state.get("intake")
                    
                        return {
                            "messages": [tool_msg],
                            "intake": next_intake,
                            "feasibility_result": validation.feasibility or state.get("feasibility_result"),
                            "calendar_blocks": state.get("calendar_blocks"),
                            "scheduling_context": state.get("scheduling_context"),
                            "executed_tool_signatures": executed_signatures,
                        }

                    # Accepted feedback is a valid pending checkpoint. Keep it so
                    # the repair turn starts from contract truth, not raw transcript.
                    accepted_state = {
                        "intake": clean_intake_data,
                        "feasibility_result": validation.feasibility or state.get("feasibility_result"),
                        "calendar_blocks": state.get("calendar_blocks"),
                        "scheduling_context": state.get("scheduling_context"),
                        "executed_tool_signatures": executed_signatures,
                    }

                    if validation.code != "ok":
                        return {
                            **accepted_state,
                            "messages": [tool_msg],
                        }

                    # A clean checkpoint can show the model's student-facing reply.
                    return {
                        **accepted_state,
                        "messages": [tool_msg, AIMessage(content=output_message)],
                    }

                tool_messages.append(await execute_regular_tool(tool_call))
            logger.info(
                "[PERF][INTAKE] tools_node end duration_ms=%s returned_messages=%s",
                elapsed_ms(tools_node_started_at),
                len(tool_messages),
            )
            return {
                "messages": tool_messages,
                "executed_tool_signatures": executed_signatures,
            }

        def route_after_agent(state: IntakeState):
            """Route to tools when the agent emitted tool calls, otherwise finish."""

            if intake_is_ready_for_handoff(state.get("intake")):
                return END

            last_message = state["messages"][-1]

            if isinstance(last_message, AIMessage) and last_message.tool_calls:
                return "tools"

            return END

        def route_after_tools(state: IntakeState):
            """Continue looping until the turn is complete or the safety valve trips.

            The loop ends when:
            - intake is ready for handoff
            - the worker produced a plain AI reply with no more tool calls
            - the safety valve prevents pathological looping
            """

            # Safety valve: max 100 turns per session
            if state.get("turn_count", 0) >= 18:
                logger.warning(f"[INTAKE] Max turns reached ({state['turn_count']}) — forcing end")
                return END

            last_message = state["messages"][-1]
            if isinstance(last_message, AIMessage) and not getattr(last_message, "tool_calls", None):
                return END

            return "agent"

        # Minimal two-node loop:
        # START -> agent -> tools -> agent ... -> END
        graph = StateGraph(IntakeState)

        graph.add_node("agent", call_agent)
        graph.add_node("tools", call_tools)

        graph.add_edge(START, "agent")

        graph.add_conditional_edges(
            "agent",
            route_after_agent,
            {
                "tools": "tools",
                END: END,
            },
        )
        graph.add_conditional_edges(
            "tools",
            route_after_tools,
            {
                "agent": "agent",
                END: END,
            },
        )

        return graph.compile()

@traceable(run_type="chain", name="intake_interactive_session")
async def run_interactive_session(user_id: str = "test_user_99"):
    """Run a local terminal session for manual Intake testing."""

    import uuid

    session_id = str(uuid.uuid4())[:8]
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"convo_intake_{session_id}.log")

    turn_count = 0

    def serialize_message(message: BaseMessage) -> dict:
        """Convert LangChain messages into JSON-friendly log records."""

        content = getattr(message, "content", "")
        if isinstance(content, str):
            try:
                parsed = json.loads(content)
                content = parsed
            except Exception:
                pass

        item = {
            "type": message.__class__.__name__,
            "content": content,
        }
        if getattr(message, "name", None):
            item["name"] = message.name
        if getattr(message, "tool_calls", None):
            item["tool_calls"] = message.tool_calls
        if getattr(message, "tool_call_id", None):
            item["tool_call_id"] = message.tool_call_id
        return item

    def write_log(event_type: str, content: Any) -> None:
        """Append one structured event to the interactive session log."""

        with open(log_file, "a", encoding="utf-8") as f:
            entry = {
                "timestamp": datetime.now().isoformat(),
                "turn": turn_count,
                "event_type": event_type,
                "content": content,
            }
            f.write(json.dumps(entry, ensure_ascii=False, default=str, indent=2))
            f.write("\n\n" + "=" * 80 + "\n\n")

    state = {
        "messages": [],
        "user_id": user_id,
        "user_context": "",
        "intake": None,
        "feasibility_result": None,
        "calendar_blocks": None,
        "active_plan_context": None,
        "scheduling_context": None,
        "turn_count": 0,
        "executed_tool_signatures": [],
    }

    app = None
    print("SkedioAI Intake started. Type 'exit' to stop.\n")
    print(f"Palantir Intake Logging Enabled: {log_file}\n")
    write_log(
        "SYSTEM_START",
        {
            "user_id": user_id,
            "model": "gpt-5-mini",
            "debug_enabled": INTAKE_DEBUG,
        },
    )

    while True:
        user_input = input("You: ").strip()

        if user_input.lower() in {"exit", "quit", "q"}:
            write_log("USER_INPUT", "quit")
            print("Exiting.")
            break

        turn_count += 1
        turn_started_at = time.time()
        write_log("USER_INPUT", user_input)
        old_message_count = len(state["messages"])
        state["messages"].append(HumanMessage(content=user_input))

        try:
            if app is None:
                from langchain_openai import ChatOpenAI

                llm = ChatOpenAI(
                    model="gpt-5-mini",
                    temperature=0.2,
                    api_key=os.getenv("OPENAI_API_KEY"),
                    reasoning_effort="low",   
                    verbosity="low",          
                )
                agent = IntakeAgent(llm_client=llm)
                app = agent.intake_agent()

            result = await app.ainvoke(state)
            state.update(result)
            new_messages = [serialize_message(m) for m in state["messages"][old_message_count:]]

            last_message = state["messages"][-1]

            if isinstance(last_message, AIMessage):
                print(f"\nSkedioAI: {last_message.content}\n")
            else:
                print(f"\nSkedioAI: {last_message}\n")

            write_log(
                "INTAKE_TURN",
                {
                    "new_messages": new_messages,
                    "intake_ready": intake_is_ready_for_handoff(state.get("intake")),
                    "status": state["intake"].status if state.get("intake") else None,
                    "intake": state["intake"].model_dump() if state.get("intake") else None,
                    "duration_seconds": round(time.time() - turn_started_at, 3),
                },
            )

            if intake_is_ready_for_handoff(state.get("intake")):
                print("✅ Intake ready.")
                print("\nFinal Intake Output:")

                print(json.dumps(state["intake"].model_dump(), indent=2))

                write_log(
                    "INTAKE_READY",
                    {
                        "intake": state["intake"].model_dump(),
                    },
                )

                break

        except Exception as e:
            write_log(
                "ERROR",
                {
                    "error": str(e),
                    "error_type": e.__class__.__name__,
                    "traceback": traceback.format_exc(),
                    "duration_seconds": round(time.time() - turn_started_at, 3),
                },
            )
            print(f"\nError: {e}\n")
            break

    write_log("SYSTEM_END", {"turns": turn_count, "intake_ready": intake_is_ready_for_handoff(state.get("intake"))})

if __name__ == "__main__":
    asyncio.run(run_interactive_session())
