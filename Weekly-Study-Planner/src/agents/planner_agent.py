"""Planner agent for producing, verifying, and committing timed study plans.

This file owns the scheduling part of the product.

Mental model:
- Intake decides *what* the student needs and the planning constraints.
- Planner decides *where and when* study sessions can fit.
- The graph here turns a locked intake contract plus scheduling context into a
  candidate plan, runs deterministic verification, and commits only when safe.
"""

from langchain_core.messages.base import BaseMessage
import os
import logging
import sys

try:
    from langchain.agents import create_agent
    from langchain.agents.structured_output import ToolStrategy
except ImportError:
    raise ImportError(
        "planner_agent requires langchain>=0.3.x with create_agent support. "
        "Install with: pip install 'langchain>=0.3.0'"
    )

import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
import asyncio
import time

from langchain_openai import ChatOpenAI

from langchain_core.tools import tool
from src.prompts.planner.prompt import draft_agent_prompt
from src.services.planner_verifier import verify_plan
from src.services.planner_context import (
    build_intake_snapshot_for_commit,
    build_planner_context,
    fill_computed_fields,
    planner_remaining_subtopics_from_state,
    planner_chapters,
    planner_subjects,
    planner_work_item_targets,
    render_planner_human_message,
)
from src.models.intake import IntakeAgentOutput
from src.models.planner import (
    PlannerOutput,
    PlannerRequest,
    PlannerState,
    StudyPlan,
)

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage

from langgraph.graph import StateGraph, START, END
from typing import Literal
from langgraph.graph.message import add_messages
from langsmith import traceable

load_dotenv()

logger = logging.getLogger(__name__)

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "skedioai-final-eval-v1"
os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGCHAIN_API_KEY", "")

for key in ("GOOGLE_API_KEY", "GROQ_API_KEY"):
    value = os.getenv(key)
    if value:
        os.environ[key] = value
model = ChatOpenAI(
    model="gpt-5-mini",
    temperature=0.2,
    api_key=os.getenv("OPENAI_API_KEY"),
    reasoning_effort="low",
    verbosity="low",
)


def _parse_planner_output(structured: Any) -> PlannerOutput | None:
    """Normalize LangChain structured output into `PlannerOutput`."""

    if structured is None:
        return None
    if isinstance(structured, PlannerOutput):
        return structured
    if isinstance(structured, dict):
        return PlannerOutput(**structured)
    raise TypeError(f"Unexpected structured_response type: {type(structured)}")


def _build_planner_result_update(
    *,
    planner_output: PlannerOutput | None,
    planner_context: Dict[str, Any],
) -> Dict[str, Any]:
    """Map planner structured output into the graph state update."""

    unverified_plan = None
    planner_message = ""
    status = "pending"

    if planner_output is not None:
        planner_message = planner_output.message
        unverified_plan = planner_output.plan

        if planner_output.status == "draft_ready" and unverified_plan is None:
            status = "rejected"
            planner_message = "Planner returned draft_ready without a plan."

        if planner_output.status == "needs_input":
            status = "needs_input"
            unverified_plan = None

        if planner_output.status == "failed":
            status = "rejected"
            unverified_plan = None

        if unverified_plan is not None:
            unverified_plan = fill_computed_fields(unverified_plan, planner_context)

    returned_messages: List[BaseMessage] = []
    if planner_message:
        returned_messages.append(AIMessage(content=planner_message))

    state_update: Dict[str, Any] = {
        "messages": returned_messages,
        "planner_status": status,
        "unverified_plan": unverified_plan,
    }
    if status == "rejected":
        state_update["verified_plan"] = None
        state_update["unverified_plan"] = None

    return state_update


def _planner_uses_active_plan(state: PlannerState) -> bool:
    """Return whether planner should operate as a schedule revision worker."""

    return state.has_active_plan or state.auto_mode





def planner_state_from_input(
    planner_input: PlannerRequest | Dict[str, Any],
    *,
    commit_requested: bool = False,
    messages: Optional[List[BaseMessage]] = None,
    user_context: Optional[str] = None,
    verified_plan: Optional[StudyPlan | Dict[str, Any]] = None,
    has_active_plan: bool = False,
    active_plan_id: Optional[str] = None,
) -> PlannerState:
    """Build PlannerState from the final Planner Input boundary."""

    parsed_input = (
        planner_input
        if isinstance(planner_input, PlannerRequest)
        else PlannerRequest.model_validate(planner_input)
    )

    return PlannerState(
        request=parsed_input,
        commit_requested=commit_requested,
        messages=messages or [],
        committed=False,
        planner_status=None,
        user_context=user_context,
        has_active_plan=has_active_plan,
        active_plan_id=active_plan_id,
        clashes=None,
        verified_plan=(
            verified_plan
            if isinstance(verified_plan, StudyPlan) or verified_plan is None
            else StudyPlan.model_validate(verified_plan)
        ),
    )


def load_demo_planner_input_from_json(
    relative_path: str = "data_models/planner_request_demo.json",
) -> Dict[str, Any]:
    """Load the local demo PlannerRequest fixture for planner-only testing."""

    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    planner_request_path = os.path.join(project_root, relative_path)

    with open(planner_request_path, "r", encoding="utf-8") as f:
        planner_request_payload = json.load(f)

    return PlannerRequest.model_validate(planner_request_payload).model_dump()


def load_create_planner_input_from_demo(
    *,
    user_id: str,
    relative_path: str = "data_models/planner_request_demo.json",
) -> Dict[str, Any]:
    """Load the create-plan demo fixture, but replace the runtime user id."""

    planner_input = load_demo_planner_input_from_json(relative_path=relative_path)
    planner_input["user_id"] = user_id
    return PlannerRequest.model_validate(planner_input).model_dump()


def load_reschedule_planner_input_from_active_plan(
    *,
    user_id: str,
) -> Dict[str, Any]:
    """Build PlannerRequest from the user's current active plan snapshot.

    This keeps the revision contract aligned with the same active-plan snapshot
    that runtime state passes into the planner worker.
    """

    from src.services.active_plan import (
        build_mock_active_plan_snapshot,
        get_active_plan_snapshot,
    )

    if os.getenv("SAATHI_USE_MOCK_ACTIVE_PLAN") == "1":
        active_plan = build_mock_active_plan_snapshot()
    else:
        active_plan = get_active_plan_snapshot(user_id)

    if not active_plan.get("has_plan") or not active_plan.get("plan_details"):
        raise ValueError(f"No active plan found for user_id={user_id}")

    plan_details = active_plan["plan_details"]
    intake_snapshot = plan_details.get("intake_snapshot") or {}
    intake = IntakeAgentOutput.model_validate(intake_snapshot)

    availability = intake_snapshot.get("availability") or {}
    scheduling_context = {
        "timezone": availability.get("timezone"),
        "daily_study_hours": availability.get("daily_study_hours") or {},
        "time_blocks": availability.get("time_blocks") or {},
    }

    return PlannerRequest(
        user_id=user_id,
        intake=intake,
        scheduling_context=scheduling_context,
        active_plan_context=active_plan,
    ).model_dump()




# TOOLS

@tool
async def commit_plan(
    user_id: str,
    plan: StudyPlan,
    work_item_targets: Dict[str, float] = None,
    backlog_match_keys: List[str] = None,
    intake_snapshot: Dict[str, Any] = None,
    wait_for_backlog_sync: bool = False,
) -> dict:
    """
    Commit plan to Neo4j using V2 Session-based architecture.
    Plan → Day → Session → Content → Chapter Backlog
    """
    from src.services.plan_commit import commit_study_plan

    return await commit_study_plan(
        user_id=user_id,
        plan=plan,
        work_item_targets=work_item_targets,
        backlog_match_keys=backlog_match_keys,
        intake_snapshot=intake_snapshot,
        wait_for_backlog_sync=wait_for_backlog_sync,
    )

_planner_graph_cache: dict[str, Any] = {}


def create_planner_graph(user_context: str = ""):
    """Create the Planner graph for drafting, verifying, and committing plans.

    High-level state machine:
    - `planner_node` asks the model for a plan draft or revision
    - `verify_node` runs deterministic checks on the draft
    - `commit_node` persists only verified plans
    - `escalate_node` handles auto-mode overflow/conflict cases
    """

    cache_key = user_context or ""
    cached_graph = _planner_graph_cache.get(cache_key)
    if cached_graph is not None:
        return cached_graph

    workflow = StateGraph(PlannerState)

    draft_agent = create_agent(
        model=model,
        tools=[],
        system_prompt=draft_agent_prompt(
            user_id=None, user_context=user_context
        ),
        response_format=ToolStrategy(PlannerOutput),
    )

    def _build_planner_worker_input_messages(state: PlannerState) -> List[BaseMessage]:
        """Build the single planner worker message stack for create or revise."""

        runtime_user_id = getattr(getattr(state, "request", None), "user_id", None) or "unknown"
        planner_context = build_planner_context(state)
        if _planner_uses_active_plan(state):
            from src.services.reschedule_context import (
                build_reschedule_plan_context,
                render_reschedule_plan_context_message,
            )

            plan_context = build_reschedule_plan_context(state)
            return [
                HumanMessage(
                    content=(
                        "[RUNTIME PLANNER CONTEXT]\n"
                        f"user_id: {runtime_user_id}\n"
                        "mode: revise\n"
                        "When a decision needs user_id, use this exact value."
                    )
                ),
                HumanMessage(
                    content=render_reschedule_plan_context_message(plan_context)
                ),
                HumanMessage(
                    content=(
                        "[VISIBLE CHAT HISTORY]\n"
                        "Use the following messages for the user's latest feedback and preferences. "
                        "Do not use chat history to override locked Intake fields."
                    )
                ),
                *state.messages,
            ]

        runtime_now = datetime.now().strftime("%Y-%m-%d %H:%M")
        planner_context["runtime"] = {"current_datetime": runtime_now}
        return [
            HumanMessage(
                content=(
                    "[RUNTIME PLANNER CONTEXT]\n"
                    f"user_id: {runtime_user_id}\n"
                    "mode: create\n"
                    f"current_datetime: {runtime_now}\n"
                    "When a decision needs user_id, use this exact value."
                )
            ),
            HumanMessage(
                content=render_planner_human_message(state, planner_context)
            ),
            HumanMessage(
                content=(
                    "[VISIBLE CHAT HISTORY]\n"
                    "Use the following messages for the user's latest feedback and preferences. "
                    "Do not use chat history to override locked Intake fields."
                )
            ),
            *state.messages,
        ]

    async def _run_planner_worker(state: PlannerState) -> Dict[str, Any]:
        """Run the canonical planner worker with mode-specific context only."""

        planner_context = build_planner_context(state)
        worker_input_messages = _build_planner_worker_input_messages(state)
        result = await draft_agent.ainvoke({"messages": worker_input_messages})
        logger.debug("Draft agent returned keys=%s", list(result.keys()))
        planner_output = _parse_planner_output(result.get("structured_response"))
        return _build_planner_result_update(
            planner_output=planner_output,
            planner_context=planner_context,
        )

    @traceable(run_type="chain", name="planner_node")
    async def planner_node(state: PlannerState):
        """Shared planner entry for both first-plan creation and revision."""

        state_update = await _run_planner_worker(state)

        try:
            from langsmith.run_trees import get_current_run_tree

            run = get_current_run_tree()
            if run:
                run.add_metadata({
                    "planner.commit_requested": state.commit_requested,
                    "planner.mode": "revise" if _planner_uses_active_plan(state) else "create",
                    "planner.planner_status": state_update.get("planner_status"),
                    "planner.committed": state.committed,
                    "planner.auto_mode": state.auto_mode,
                    "planner.has_overflow": state.has_overflow,
                    "intake.subjects": planner_subjects(state),
                    "intake.chapters": planner_chapters(state),
                    "intake.work_item_targets": planner_work_item_targets(state),
                    "intake.remaining_subtopics": planner_remaining_subtopics_from_state(state),
                })
        except Exception:
            pass

        return state_update

    @traceable(run_type="chain", name="verify node")
    async def verify_node(state: PlannerState):
        """Run deterministic verification against the unverified draft.

        This is the key quality gate: the LLM can draft, but only the verifier
        decides whether the draft is structurally acceptable.
        """

        next_attempt = state.verify_attempts + 1
        if state.unverified_plan is None:
            return {
                "messages": [
                    AIMessage(
                        content="Verifier did not receive an unverified plan to check."
                    )
                ],
                "verify_errors": {
                    "passed": False,
                    "error_count": 1,
                    "errors": [
                        {
                            "type": "missing_unverified_plan",
                            "message": "No unverified_plan exists in planner state.",
                        }
                    ],
                },
                "verify_attempts": next_attempt,
                "planner_status": "rejected" if next_attempt >= 3 else "pending",
            }

        planner_context = build_planner_context(state)
        runtime_now = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        result = verify_plan(
            state.unverified_plan,
            planner_context,
            now=runtime_now,
        )
        if result.get("passed"):
            return {
                "messages": [
                    AIMessage(
                        content="Plan passed deterministic verification and is ready for review."
                    )
                ],
                "planner_status": "awaiting_approval",
                "verified_plan": state.unverified_plan,
                "unverified_plan": None,
                "verify_errors": None,
            }

        repair_message = (
            "The draft plan failed deterministic verification. Repair the plan using "
            "these exact verifier errors. Do not change the locked Intake contract.\n\n"
            + json.dumps(result, separators=(",", ":"), default=str)
        )

        return {
            "messages": [AIMessage(content=repair_message)],
            "planner_status": "rejected" if next_attempt >= 3 else "pending",
            "unverified_plan": None,
            "verify_errors": result,
            "verify_attempts": next_attempt,
        }

    @traceable(run_type="chain", name="escalate_node")
    async def escalate_node(state: PlannerState):
        """Escalate failed auto-reschedule conflicts to a manual notification."""

        if not state.auto_mode:
            return {"messages": state.messages}

        from src.api.calendar_webhook import send_conflict_email

        clashes = getattr(state, "clashes", [])
        agent_response = state.messages[-1].content if state.messages else ""

        send_conflict_email(
            clashes,
            "couldn't auto reschedule- manual action needed",
            user_id=state.request.user_id,
            agent_response=agent_response,
        )

        return {"messages": state.messages, "has_overflow": True}

    @traceable(run_type="chain", name="commit node")
    async def commit_node(state: PlannerState):
        """Commit a verified plan and persist its Intake snapshot.

        Commit should be the first place that mutates durable plan storage.
        Everything before this node is still draft/review work.
        """

        from src.database.neo4j import Neo4jManager
        from src.services.plan_commit import ensure_commit_logging

        commit_logger = ensure_commit_logging()
        user_id = state.request.user_id
        node_commit_id = f"commit_node_{datetime.now().strftime('%H%M%S_%f')}"
        commit_started = time.perf_counter()
        commit_logger.info(
            "commit_id=%s step=commit_node status=start user_id=%s commit_requested=%s verified_plan=%s message_count=%s",
            node_commit_id,
            user_id,
            state.commit_requested,
            getattr(state.verified_plan, "plan_id", None),
            len(state.messages or []),
        )

        # Extract active plan context for revise-plan backlog flagging (V2)
        existing_sessions = set()
        commit_logger.info(
            "commit_id=%s step=neo4j_manager_init status=start scope=commit_node",
            node_commit_id,
        )
        neo4j = Neo4jManager()
        commit_logger.info(
            "commit_id=%s step=neo4j_manager_init status=success scope=commit_node",
            node_commit_id,
        )

        commit_logger.info(
            "commit_id=%s step=extract_existing_sessions status=start has_active_plan=%s",
            node_commit_id,
            state.has_active_plan,
        )
        current_active_plan = getattr(getattr(state, "request", None), "active_plan_context", None) or {}
        current_plan_details = current_active_plan.get("plan_details") or {}
        if _planner_uses_active_plan(state):
            try:
                for day in current_plan_details.get("days", []):
                    for session in day.get("sessions", []):
                        for content in session.get("contents", []):
                            if content.get("match_key"):
                                existing_sessions.add(content["match_key"])
            except Exception as e:
                logger.warning(f"Failed to extract existing sessions: {e}")
                commit_logger.warning(
                    "commit_id=%s step=extract_existing_sessions status=failed_non_critical error=%s",
                    node_commit_id,
                    e,
                )
        current_active_plan_id = current_plan_details.get("plan_id") or current_active_plan.get("plan_id")
        commit_logger.info(
            "commit_id=%s step=extract_existing_sessions status=success count=%s",
            node_commit_id,
            len(existing_sessions),
        )

        try:
            if not state.verified_plan:
                raise Exception("Cannot commit plan before deterministic verification passes")

            plan = state.verified_plan
            logger.info(f"Using verified_plan for commit: {plan.plan_id}")
            commit_logger.info(
                "commit_id=%s step=verified_plan_check status=success plan_id=%s day_count=%s total_hours=%s",
                node_commit_id,
                plan.plan_id,
                len(plan.days or []),
                plan.total_hours,
            )

            if not plan.days or len(plan.days) == 0:
                raise Exception("No days found in plan")

            # Flag backlog content when revising an existing active plan
            if _planner_uses_active_plan(state) and existing_sessions:
                commit_logger.info(
                    "commit_id=%s step=reschedule_backlog_flagging status=start existing_session_keys=%s",
                    node_commit_id,
                    len(existing_sessions),
                )
                for day in plan.days:
                    for session in day.sessions:
                        for content in session.contents:
                            if (
                                content.match_key
                                and content.match_key in existing_sessions
                            ):
                                logger.info(
                                    f"[COMMIT] Content {content.match_key} marked as backlog (revision)"
                                )
                commit_logger.info(
                    "commit_id=%s step=reschedule_backlog_flagging status=success",
                    node_commit_id,
                )

            # For first-time plans, log all sessions
            if not _planner_uses_active_plan(state):
                content_count = 0
                for day in plan.days:
                    for session in day.sessions:
                        for content in session.contents:
                            content_count += 1
                            logger.info(
                                f"[COMMIT] Content {content.match_key} - is_backlog={False} (create mode)"
                            )
                commit_logger.info(
                    "commit_id=%s step=create_plan_content_scan status=success content_count=%s",
                    node_commit_id,
                    content_count,
                )

            commit_logger.info(
                "commit_id=%s step=build_intake_snapshot_for_commit status=start",
                node_commit_id,
            )
            intake_snapshot = build_intake_snapshot_for_commit(state)
            commit_logger.info(
                "commit_id=%s step=build_intake_snapshot_for_commit status=success snapshot_keys=%s",
                node_commit_id,
                sorted(list(intake_snapshot.keys())) if isinstance(intake_snapshot, dict) else [],
            )

            commit_logger.info(
                "commit_id=%s step=commit_plan_tool status=start plan_id=%s",
                node_commit_id,
                plan.plan_id,
            )
            result = await commit_plan.ainvoke({
                "user_id": user_id,
                "plan": plan,
                "work_item_targets": planner_work_item_targets(state),
                "backlog_match_keys": planner_remaining_subtopics_from_state(state),
                "intake_snapshot": intake_snapshot,
            })
            commit_logger.info(
                "commit_id=%s step=commit_plan_tool status=returned result_success=%s result_plan_id=%s sessions_created=%s",
                node_commit_id,
                result.get("success"),
                result.get("plan_id"),
                result.get("sessions_created"),
            )

            if not result.get("success"):
                raise Exception(result.get("error"))

            commit_logger.info(
                "commit_id=%s step=mark_other_plans_inactive status=start keep_plan_id=%s",
                node_commit_id,
                result["plan_id"],
            )
            archived_count = neo4j.mark_other_plans_inactive(
                user_id,
                result["plan_id"],
            )
            commit_logger.info(
                "commit_id=%s step=mark_other_plans_inactive status=success archived_count=%s",
                node_commit_id,
                archived_count,
            )
            if archived_count:
                logger.info(
                    "Archived %s previous active plan(s) after committing %s",
                    archived_count,
                    result["plan_id"],
                )

            # ── Change Log ──
            try:
                from src.database.neo4j import Neo4jManager

                commit_logger.info(
                    "commit_id=%s step=change_log status=start",
                    node_commit_id,
                )
                neo4j = Neo4jManager()
                today = datetime.now().strftime("%Y-%m-%d")

                if _planner_uses_active_plan(state) and current_active_plan_id:
                    neo4j.append_to_change_log(
                        user_id,
                        f"{today}: ACTIVE PLAN {current_active_plan_id} RESCHEDULED - replaced by {result.get('plan_id')}",
                    )

                creation_entry = f"{today}: NEW PLAN {result.get('plan_id')} CREATED via {'revision' if _planner_uses_active_plan(state) else 'intake'}"
                if _planner_uses_active_plan(state) and current_active_plan_id:
                    creation_entry += f" (from active: {current_active_plan_id})"
                neo4j.append_to_change_log(user_id, creation_entry)
                commit_logger.info(
                    "commit_id=%s step=change_log status=success entry=%s",
                    node_commit_id,
                    creation_entry,
                )

            except Exception as log_err:
                logger.warning(f"Failed to update change_log: {log_err}")
                commit_logger.warning(
                    "commit_id=%s step=change_log status=failed_non_critical error=%s",
                    node_commit_id,
                    log_err,
                )

            # ── Episodic Memory ──
            try:
                from src.database.vector_store import VectorStore

                commit_logger.info(
                    "commit_id=%s step=episodic_memory status=start",
                    node_commit_id,
                )
                vs = VectorStore()

                # Get subjects from scheduled allocations; content nodes are now
                # deliberately lean and do not repeat subject/chapter metadata.
                subjects_in_plan = set()
                for day in plan.days:
                    for session in day.sessions:
                        for allocation in session.allocated_hours:
                            subjects_in_plan.add(allocation.subject)

                subjects_in_plan = list(subjects_in_plan)
                total_days = len(plan.days)
                total_hours = plan.total_hours
                avg_hours_per_day = total_hours / total_days if total_days > 0 else 0
                reason = "New Study Plan"
                intensity = (
                    "light"
                    if avg_hours_per_day < 2
                    else "normal"
                    if avg_hours_per_day < 4
                    else "intense"
                )
                metadata_type = "reschedule" if _planner_uses_active_plan(state) else "plan_create"

                if not _planner_uses_active_plan(state):
                    await vs.log_plan_created(
                        user_id=user_id,
                        plan_id=result["plan_id"],
                        topics=subjects_in_plan,
                        total_hours=total_hours,
                        intensity=intensity.upper(),
                    )
                else:
                    await asyncio.gather(
                        vs.log_event(
                            user_id=user_id,
                            event_type="plan_rescheduled",
                            text=f"Reschedule reason: {reason}",
                            metadata={
                                "reason": reason,
                                "active_plan": current_active_plan_id or "",
                            },
                        ),
                        vs.log_plan_created(
                            user_id=user_id,
                            plan_id=result["plan_id"],
                            topics=subjects_in_plan,
                            total_hours=total_hours,
                            intensity=intensity.upper(),
                        ),
                    )

                logger.info(
                    f" Logged {metadata_type}: {intensity} plan with {', '.join(subjects_in_plan)}"
                )
                commit_logger.info(
                    "commit_id=%s step=episodic_memory status=success metadata_type=%s intensity=%s topics=%s",
                    node_commit_id,
                    metadata_type,
                    intensity,
                    subjects_in_plan,
                )

            except Exception as mem_err:
                logger.warning(
                    f"⚠️ Failed to save episodic log (Non-critical): {mem_err}"
                )
                commit_logger.warning(
                    "commit_id=%s step=episodic_memory status=failed_non_critical error=%s",
                    node_commit_id,
                    mem_err,
                )

            # ── Learner Memory Synthesis Trigger ──
            try:
                from src.memory.triggers import schedule_plan_accepted_memory_synthesis

                commit_logger.info(
                    "commit_id=%s step=plan_accepted_memory_trigger status=start",
                    node_commit_id,
                )
                scheduled = schedule_plan_accepted_memory_synthesis(user_id=user_id)
                commit_logger.info(
                    "commit_id=%s step=plan_accepted_memory_trigger status=success scheduled=%s",
                    node_commit_id,
                    scheduled,
                )
            except Exception as trigger_err:
                logger.warning(
                    "Plan accepted memory trigger skipped user_id=%s error=%s",
                    user_id,
                    trigger_err,
                )
                commit_logger.warning(
                    "commit_id=%s step=plan_accepted_memory_trigger status=failed_non_critical error=%s",
                    node_commit_id,
                    trigger_err,
                )

            commit_logger.info(
                "commit_id=%s step=commit_node status=success committed_plan_id=%s duration_s=%.2f",
                node_commit_id,
                result["plan_id"],
                time.perf_counter() - commit_started,
            )

            return {
                "messages": [AIMessage(content=f"{result['message']}")],
                "planner_status": "committed",
                "committed": True,
            }

        except Exception as e:
            import traceback

            error_details = traceback.format_exc()
            logger.error(f"Commit failed: {error_details}")
            commit_logger.error(
                "commit_id=%s step=commit_node status=failed duration_s=%.2f error=%s",
                node_commit_id,
                time.perf_counter() - commit_started,
                e,
            )
            return {
                "messages": [
                    AIMessage(
                        content=f"❌ Failed to commit plan: {str(e)}\n\nPlease try rephrasing your approval or say 'yes' again."
                    )
                ],
                "planner_status": "rejected",
                "committed": False,
            }

    def route_start(state):
        """Choose the first planner node from the requested action."""

        if state.commit_requested:
            return "commit"
        return "planner_node"

    def after_planner(state: PlannerState):
        if state.unverified_plan is not None:
            return "verify_node"
        return END

    def after_verify(state: PlannerState):
        if state.verified_plan is not None:
            return END

        if state.verify_attempts < 3:
            return "planner_node"

        return END


    workflow.add_conditional_edges(
    START,
    route_start,
    {
        "planner_node": "planner_node",
        "commit": "commit",
    },
)

    workflow.add_node("planner_node", planner_node)
    workflow.add_node("verify_node", verify_node)
    workflow.add_node("commit", commit_node)
    workflow.add_node("escalate", escalate_node)

    workflow.add_conditional_edges(
    "planner_node",
    after_planner,
    {
        "verify_node": "verify_node",
        END: END,
    },
)

    workflow.add_conditional_edges(
    "verify_node",
    after_verify,
    {
        "planner_node": "planner_node",
        END: END,
    },
)

    workflow.add_edge("commit", END)
    workflow.add_edge("escalate", END)

    compiled = workflow.compile()
    _planner_graph_cache[cache_key] = compiled
    return compiled



if __name__ == "__main__":
    import sys
    import asyncio
    from datetime import datetime

    def _prompt_yes_no(prompt: str, *, default: bool = False) -> bool:
        """Return a normalized yes/no answer from the terminal."""

        raw = input(prompt).strip().lower()
        if not raw:
            return default
        return raw in {"y", "yes"}

    def _prompt_mode() -> str:
        """Read and validate the harness mode selection."""

        choice = input("\nEnter choice (1/2/3/4): ").strip()
        if choice not in {"1", "2", "3", "4"}:
            print("❌ Invalid choice. Exiting.")
            sys.exit(1)
        return choice

    def _load_reschedule_harness_input() -> tuple[Dict[str, Any], str, str]:
        """Load planner input for reschedule mode from either real or mock active plan."""

        user_id = input("Enter user_id for active plan lookup [samosa]: ").strip() or "samosa"
        use_mock = _prompt_yes_no("Use mock active plan? (y/N): ", default=False)

        if use_mock:
            os.environ["SAATHI_USE_MOCK_ACTIVE_PLAN"] = "1"
            source = "mock_active_plan"
            print("\n🧪 Using mock active plan for reschedule mode.")
        else:
            os.environ.pop("SAATHI_USE_MOCK_ACTIVE_PLAN", None)
            source = "real_active_plan"
            print(f"\n📋 Using real active plan for user_id={user_id}.")

        try:
            planner_input = load_reschedule_planner_input_from_active_plan(user_id=user_id)
        except Exception as exc:
            print(f"\n❌ Failed to load reschedule input for user_id={user_id}: {exc}")
            sys.exit(1)

        return planner_input, user_id, source

    def _load_create_harness_input() -> tuple[Dict[str, Any], str, str]:
        """Load create-plan input using the terminal-provided runtime user id."""

        user_id = input("Enter user_id for create-plan run [samosa]: ").strip() or "samosa"
        planner_input = load_create_planner_input_from_demo(user_id=user_id)
        os.environ.pop("SAATHI_USE_MOCK_ACTIVE_PLAN", None)
        return planner_input, user_id, "demo_planner_request"

    def _load_intake_ca57994c_harness_input() -> tuple[Dict[str, Any], str, str]:
        """Load the approved Intake fixture from convo_intake_ca57994c."""

        planner_input = load_demo_planner_input_from_json(
            "data_models/planner_request_intake_ca57994c.json"
        )
        os.environ.pop("SAATHI_USE_MOCK_ACTIVE_PLAN", None)
        return planner_input, planner_input["user_id"], "intake_ca57994c_planner_request"

    async def main():
        """Run the local interactive Planner harness."""

        print("=" * 60)
        print("   WEEKLY PLANNER AGENT - TEST SUITE")
        print("=" * 60)

        planner_input = load_demo_planner_input_from_json()
        print("1. CREATE_PLAN - Build fresh 7-day plan")
        print("2. RESCHEDULE - Adjust existing active plan")
        print("3. CUSTOM - Enter your own scenario")
        print("4. INTAKE_CA57994C - Use the latest approved Intake contract fixture")

        choice = _prompt_mode()
        harness_user_id = planner_input.get("user_id", "demo-user")
        active_plan_source = "demo_planner_request"

        if choice == "1":
            TEST_MODE = "create_plan"
            test_message = None
            planner_input, harness_user_id, active_plan_source = _load_create_harness_input()
        elif choice == "2":
            TEST_MODE = "reschedule"
            planner_input, harness_user_id, active_plan_source = _load_reschedule_harness_input()
            test_message = (
                """I missed one planned session and need the remaining work rearranged around my current calendar. Keep the locked scope the same and only rebuild the future schedule.
""")
        elif choice == "3":
            TEST_MODE = input("Enter mode (create_plan/reschedule): ").strip()
            if TEST_MODE not in {"create_plan", "reschedule"}:
                print("❌ Invalid mode. Use create_plan or reschedule.")
                sys.exit(1)
            test_message = (
                input("Enter initial message (or press Enter to skip): ").strip()
                or None
            )
            if TEST_MODE == "reschedule":
                planner_input, harness_user_id, active_plan_source = _load_reschedule_harness_input()
            else:
                planner_input, harness_user_id, active_plan_source = _load_create_harness_input()
        elif choice == "4":
            TEST_MODE = "create_plan"
            test_message = None
            planner_input, harness_user_id, active_plan_source = _load_intake_ca57994c_harness_input()

        print(f"\n STARTING IN MODE: [{TEST_MODE.upper()}]")
        print(f" User ID: {harness_user_id}")
        print(f" Planner Input Source: {active_plan_source}")
        print("-" * 60)

        initial_messages = []
        if test_message:
            initial_messages = [HumanMessage(content=test_message)]

        current_state = planner_state_from_input(
            planner_input,
            commit_requested=False,
            messages=initial_messages,
            user_context=""" 
""",
            has_active_plan=(TEST_MODE == "reschedule"),
        )

        app = create_planner_graph()

        import json
        import uuid
        
        session_id = str(uuid.uuid4())[:8]
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"convo_{TEST_MODE}_{session_id}.log")

        print("SkedioAI Planner started. Type 'q' to stop. Planner now returns verified drafts for review.\n")
        print(f"Palantir Planner Logging Enabled: {log_file}\n")

        turn_count = 0
        
        def write_log(event_type, content):
            """Append one structured event to the local Planner harness log."""

            with open(log_file, "a", encoding="utf-8") as f:
                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "turn": turn_count,
                    "event_type": event_type,
                    "content": content
                }
                f.write(json.dumps(log_entry, default=str, indent=4) + "\n\n" + "="*80 + "\n\n")

        def _message_content_for_log(msg):
            """Return JSON-friendly message content for harness logs."""

            msg_content = msg.content if hasattr(msg, "content") else str(msg)
            if isinstance(msg_content, str):
                try:
                    parsed_json = json.loads(msg_content)
                    return json.dumps(parsed_json, indent=2)
                except Exception:
                    return msg_content
            return msg_content

        def _planner_output_messages(messages):
            """Extract PlannerOutput.message values from structured tool calls."""

            outputs = []
            for msg in messages or []:
                tool_calls = getattr(msg, "tool_calls", None) or []
                for call in tool_calls:
                    if call.get("name") != "PlannerOutput":
                        continue
                    args = call.get("args") or {}
                    message = args.get("message")
                    if message:
                        outputs.append(str(message))
            return outputs

        def _compact_verifier_error(verify_errors):
            """Return one readable verifier error line for terminal output."""

            if not verify_errors:
                return None
            errors = verify_errors.get("errors") or []
            if not errors:
                return "Verifier failed, but no detailed error was returned."

            first = errors[0]
            error_type = first.get("type", "verification_error")
            date = first.get("date")
            session = first.get("session")
            start_time = first.get("start_time")
            message = first.get("message") or ""

            parts = [error_type]
            if date:
                parts.append(str(date))
            if start_time:
                parts.append(str(start_time))
            if session:
                parts.append(str(session))

            return " | ".join(parts) + (f" — {message}" if message else "")

        def _planner_context_for_log(state):
            """Return only available_time_windows for harness logs."""

            try:
                planner_context = build_planner_context(state)
            except Exception:
                return None

            availability = planner_context.get("availability") or {}
            return availability.get("available_time_windows")

        def _print_turn_summary(result, new_msgs, duration_seconds):
            """Print the useful planner output without dumping internal repair JSON."""

            planner_messages = _planner_output_messages(new_msgs)
            latest_planner_message = planner_messages[-1] if planner_messages else None
            verify_errors = result.get("verify_errors")
            verified_plan = result.get("verified_plan")
            committed = result.get("committed")

            if latest_planner_message:
                print(f"\nSkedioAI: {latest_planner_message}\n")
            elif committed:
                print("\nSkedioAI: Plan committed successfully.\n")
            elif verified_plan:
                print("\nSkedioAI: Plan passed verification and is ready for review.\n")
            else:
                fallback = None
                for msg in reversed(new_msgs or []):
                    if isinstance(msg, AIMessage) and msg.content:
                        content = str(msg.content)
                        if "failed deterministic verification" not in content:
                            fallback = content
                            break
                if fallback:
                    print(f"\nSkedioAI: {fallback}\n")

            status_bits = [f"{duration_seconds}s"]
            verify_attempts = result.get("verify_attempts")
            if verify_attempts is not None:
                status_bits.append(f"verify_attempts={verify_attempts}")
            if verified_plan:
                status_bits.append("verified")
            if verify_errors:
                status_bits.append("latest_draft_failed")
            if committed:
                status_bits.append("committed")
            print("Planner status: " + " | ".join(status_bits))

            compact_error = _compact_verifier_error(verify_errors)
            if compact_error:
                print(f"Verifier: {compact_error}")
            print()
                
        write_log("SYSTEM_START", f"Starting in mode: {TEST_MODE}")

        while True:
            try:
                turn_count += 1

                invoke_started_at = datetime.now()
                invoke_started_perf = time.perf_counter()
                planner_context_snapshot = _planner_context_for_log(current_state)
                write_log("TURN_START", {
                    "mode": TEST_MODE,
                    "planner_user_id": harness_user_id,
                    "active_plan_source": active_plan_source,
                    "started_at": invoke_started_at.isoformat(),
                    "message_count_before": len(current_state.messages),
                    "verify_attempts_before": current_state.verify_attempts,
                    "has_verified_plan_before": current_state.verified_plan is not None,
                    "has_unverified_plan_before": current_state.unverified_plan is not None,
                    "mock_active_plan_enabled": os.getenv("SAATHI_USE_MOCK_ACTIVE_PLAN") == "1",
                    "planner_context": planner_context_snapshot,
                })

                result = await app.ainvoke(current_state)
                invoke_ended_at = datetime.now()
                invoke_duration = round(time.perf_counter() - invoke_started_perf, 3)

                new_messages = []
                new_msgs = []
                if result["messages"]:
                    # Find messages that are new this turn by slicing off the old ones
                    old_msg_count = len(current_state.messages)
                    new_msgs = result["messages"][old_msg_count:]
                    
                    for msg in new_msgs:
                        msg_type = msg.__class__.__name__
                        msg_content = _message_content_for_log(msg)
                                
                        msg_dict = {"type": msg_type, "content": msg_content}
                        if hasattr(msg, "tool_calls") and msg.tool_calls:
                            msg_dict["tool_calls"] = msg.tool_calls
                        if hasattr(msg, "name") and msg.name:
                            msg_dict["name"] = msg.name
                            
                        new_messages.append(msg_dict)
                            
                    if not new_messages and len(result["messages"]) > 0:
                        # Fallback if no new messages were detected
                        latest_msg = result["messages"][-1]
                        new_messages.append({"type": latest_msg.__class__.__name__, "content": latest_msg.content})

                _print_turn_summary(result, new_msgs, invoke_duration)
                        
                write_log("AGENT_TURN", {
                    "started_at": invoke_started_at.isoformat(),
                    "ended_at": invoke_ended_at.isoformat(),
                    "duration_seconds": invoke_duration,
                    "planner_context": planner_context_snapshot,
                    "messages": new_messages,
                    "unverified_plan_id": getattr(result.get("unverified_plan"), "plan_id", None) if result.get("unverified_plan") else None,
                    "verified_plan_id": getattr(result.get("verified_plan"), "plan_id", None) if result.get("verified_plan") else None,
                    "verify_errors": result.get("verify_errors"),
                    "verify_attempts": result.get("verify_attempts"),
                    "status": "committed" if result.get("committed") else "ongoing"
                })

                if result.get("committed"):
                    print(f"\n{'=' * 60}")
                    print(f"   SUCCESS! PLAN COMMITTED")
                    print(f"  Mode: {TEST_MODE.upper()}")
                    print(
                        f"  Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                    print(f"{'=' * 60}")
                    break

                user_prompt_started_at = datetime.now()
                user_prompt_perf = time.perf_counter()
                user_input = input("You: ").strip()
                user_response_duration = round(time.perf_counter() - user_prompt_perf, 3)

                if user_input.lower() in ["q", "quit", "exit"]:
                    write_log("USER_INPUT", {
                        "text": "quit",
                        "started_at": user_prompt_started_at.isoformat(),
                        "ended_at": datetime.now().isoformat(),
                        "response_seconds": user_response_duration,
                    })
                    print("\n Exiting planner. No changes committed.")
                    break

                if not user_input:
                    print("⚠️  Empty input. Please type something or 'q' to quit.")
                    continue
                    
                write_log("USER_INPUT", {
                    "text": user_input,
                    "started_at": user_prompt_started_at.isoformat(),
                    "ended_at": datetime.now().isoformat(),
                    "response_seconds": user_response_duration,
                })

                current_state.messages = result["messages"] + [
                    HumanMessage(content=user_input)
                ]

                if result.get("unverified_plan"):
                    current_state.unverified_plan = result.get("unverified_plan")

                if result.get("verified_plan"):
                    current_state.verified_plan = result.get("verified_plan")

                if result.get("verify_errors") is not None:
                    current_state.verify_errors = result.get("verify_errors")

                if result.get("verify_attempts") is not None:
                    current_state.verify_attempts = result.get("verify_attempts")

            except KeyboardInterrupt:
                print("\n\n⚠️  Interrupted by user. Exiting...")
                break
            except Exception as e:
                print(f"\n❌ ERROR: {str(e)}")
                print(f" Error occurred at turn {turn_count}")
                import traceback

                traceback.print_exc()
                break

        print("\n" + "=" * 60)
        print("  SESSION ENDED")
        print("=" * 60)

    asyncio.run(main())
