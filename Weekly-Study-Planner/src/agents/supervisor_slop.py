"""
SkedioAI Supervisor Slop
======================

Minimal orchestrator for the current SkedioAI worker setup.

Turn shape:
    START
      → check_plan
      → supervisor
      → intake or planner
      → deterministic intake outcome routing or supervisor
      → user_facing
      → END

Current design:
    - Supervisor routes between intake, planner, and user-facing
    - `messages` carries full conversation history
    - `worker_envelope` stores this turn's latest worker outcome
    - `user_facing_node` is the only node that writes the final assistant reply
    - Shared state carries only cross-agent artifacts, not full worker runtime state

State glossary:
    - `worker_envelope`: latest worker packet for this turn; supervisor reads this to decide what happens next
    - `planner_status`: planner's latest workflow signal for this turn (`pending`, `needs_input`, `awaiting_approval`, `rejected`, `committed`, `escalate`)
    - `verified_plan`: verifier-approved draft for the current workflow; safe to show for review or commit
    - `committed`: whether the latest planner result was actually saved
"""

import os
import logging
import asyncio
import json
import time
from datetime import datetime
from typing import Any, Dict, TypedDict, Literal, Annotated, Optional, List


from src.database.vector_store import VectorStore
from src.database.client_cache import get_llm

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    SystemMessage,
    BaseMessage,
    RemoveMessage,
)
from langchain_core.messages.utils import trim_messages 
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import REMOVE_ALL_MESSAGES, add_messages
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI

from src.agents.intake_agent import IntakeAgent
from src.models.intake import IntakeAgentOutput
from src.services.chat_history import (
    HARD_RAW_MESSAGE_LIMIT,
    compress_chat_history,
    messages_with_summary,
)
from src.agents.envelope import AgentOutputEnvelope, create_envelope_id, make_envelope
from src.agents.stream_utils import (
    extract_worker_reply_text,
    get_writer_or_none,
    stream_llm_text,
    stream_plain_text,
)

load_dotenv()
logger = logging.getLogger(__name__)

os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGSMITH_TRACING"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "skedioai-final-eval-v1"

ROUTER_PROMPT_VERSION = "router-v2026-07-01-01"


class RoutingDecision(BaseModel):
    intent: Literal[
        "create_plan",
        "view_plan",
        "approve_plan",
        "update_plan",
        "chat",
        "unknown",
    ] = Field(
        description="What the user is trying to do."
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="0.0-1.0. Below 0.6 means the classifier is unsure — ask user to clarify."
    )
    reasoning: str = Field(description="One sentence: WHY this intent was chosen.")
    agent_chosen: Literal["intake", "planner", "user_facing"] = Field(
    description=(
        "Which agent handles this turn. "
        "user_facing' means all work for this turn is done — route to user-facing node "
        "to format the final response from the latest worker envelope."
    )
)


class WorkerOutcome(TypedDict):
    """Internal worker-control result; never exposed to the router LLM."""

    worker: Literal["intake", "planner"]
    outcome: Literal["needs_user_input", "handoff", "completed", "failed"]
    next_worker: Optional[Literal["intake", "planner"]]


class SupervisorState(TypedDict):
    pending_ui: Optional[Dict[str, Any]]
    ui_context: Optional[Dict[str, Any]]
    ui_action: Optional[Dict[str, Any]]
    user_id: str
    messages: Annotated[List[BaseMessage], add_messages]
    conversation_summary: Optional[str]
    user_context: str

    has_active_plan: bool
    active_plan_id: Optional[str]
    active_plan_context: Optional[Dict[str, Any]]
    contract_ready: bool
    draft_status: Optional[
        Literal[
            "none",
            "awaiting_review",
            "committed",
            "cancelled",
            "rejected",
        ]
    ]
    planner_mode_hint: Optional[Literal["create", "revise", "approve"]]

    routing_decision: Optional[RoutingDecision]

    intake: Optional[IntakeAgentOutput]
    scheduling_context: Optional[Dict[str, Any]]
    planner_status: Optional[
        Literal[
            "pending",
            "needs_input",
            "awaiting_approval",
            "rejected",
            "cancelled",
            "committed",
            "escalate",
        ]
    ]
    verified_plan: Optional[dict]
    committed: bool

    worker_envelope: Optional[Dict[str, Any]]
    worker_outcome: Optional[WorkerOutcome]
    worker_hops_this_turn: int
    final_reply: Optional[str]


PLAN_REVIEW_ACTIONS = [
    {"id": "approve_plan", "label": "Approve plan"},
    {"id": "request_changes", "label": "Request changes"},
    {"id": "cancel_plan", "label": "Cancel plan"},
]


async def compress_history_node(state: SupervisorState) -> dict:
    """Keep chat history bounded while preserving a rolling summary."""

    messages = list(state.get("messages") or [])
    if len(messages) < HARD_RAW_MESSAGE_LIMIT:
        return {}

    result = compress_chat_history(
        messages,
        existing_summary=state.get("conversation_summary"),
    )
    if not result.compressed:
        return {}

    logger.info(
        "[CHAT HISTORY] compressed raw_messages=%s kept_recent=%s removed=%s",
        len(messages),
        len(result.recent_messages),
        len(result.removed_messages),
    )
    return {
        "conversation_summary": result.summary,
        "messages": [
            RemoveMessage(id=REMOVE_ALL_MESSAGES),
            *result.recent_messages,
        ],
    }


ROUTER_SYSTEM_PROMPT = """
<role>
You are SkedioAI's supervisor router.

Your only job is to choose exactly one next node:
- `intake`
- `planner`
- `user_facing`

You do not collect requirements, make plans, revise plans, commit plans, or reply to the user yourself.
You only decide who should act next.
</role>

<inputs>
You may use only:
- the latest user message
- the runtime JSON
</inputs>

<available_routes>
The only valid next nodes are:
- `intake`
- `planner`
- `user_facing`
</available_routes>

<intent_space>
Return exactly one intent from this set:
- `create_plan`
- `approve_plan`
- `update_plan`
- `chat`
- `unknown`
</intent_space>

<ownership>
- `intake` owns the study contract:
  goal, subjects, scope, deadlines, time budget, availability, and feasibility constraints

- `planner` owns the schedule:
  creating a plan from a ready contract, revising a draft, changing schedule shape, and committing an approved draft

- `user_facing` owns communication:
  greetings, clarification, showing results, and safe fallback responses
</ownership>

<runtime_state_meaning>
- `has_active_plan`: whether the user already has a saved active plan
- `contract_ready`: whether intake is complete enough for planner work to begin
- `plan_verified`: whether a reviewable draft exists
- `plan_committed`: whether the plan is already finalized
- `draft_status`: supervisor-owned review lifecycle for the current draft
- `planner_mode_hint`: whether planning work looks like create, revise, or approve
- `worker_envelope`: the latest worker reply for this turn
</runtime_state_meaning>

<routing_principles>
Use these principles:

1. Decide from ownership first, then runtime state, then the latest worker reply.

2. Treat `worker_envelope.message` as the worker reply for this turn.

3. Route to `intake` when the user is creating or changing the study contract.
Examples: subjects, chapters, scope, deadline, hours, commitments, feasibility constraints

4. Route to `planner` when the contract is ready and the user wants a plan, a plan revision, or schedule-shape changes.
Examples: lighter/heavier plan, timing changes, ordering changes, more revision, more practice

5. Route to `planner` for approval-related work only when a draft exists that planner owns.

6. Route to `user_facing` when the latest worker reply should be shown to the user, or when the user message is casual, unclear, or outside worker scope.

7. Do not call a worker again in the same turn unless more worker-side processing is actually needed now.

8. If `worker_envelope.message` is a question, clarification request, confirmation request, or result meant for the user, choose `user_facing` unless the current user message clearly asks for another worker action.

</routing_principles>

<priority_rules>
When multiple rules seem relevant, decide in this order:

1. If the latest worker reply should now be conveyed to the user, choose `user_facing`.
2. If the user message is casual, ambiguous, or low-confidence, choose `user_facing`.
3. If the user is changing the study contract, choose `intake`.
4. If `contract_ready` is false and the user wants to start or continue plan creation, choose `intake`.
5. If `contract_ready` is true and the user wants planning or schedule revision, choose `planner`.
6. If `plan_verified` is true and the user is clearly approving or revising the draft, choose `planner`.
</priority_rules>

<safety>
Never:
- act like intake
- act like planner
- act like user_facing
- invent missing state
- treat vague approval as valid
- guess hidden intent from keywords alone
- route to `planner` when `contract_ready` is false
</safety>

<output>
Return `RoutingDecision` with:
- `agent_chosen`: `intake` | `planner` | `user_facing`
- `intent`: `create_plan` | `approve_plan` | `update_plan` | `chat` | `unknown`
- `confidence`: 0.0 to 1.0
- `reasoning`: one short sentence
</output>

"""



async def load_active_plan_state(user_id: str) -> Dict[str, Any]:
    try:
        from src.services.active_plan import get_active_plan_status

        result = get_active_plan_status(user_id)
        if isinstance(result, dict) and result.get("has_plan"):
            return {
                "has_active_plan": True,
                "active_plan_id": result.get("plan_id"),
                "active_plan_context": None,
            }
        return {
            "has_active_plan": False,
            "active_plan_id": None,
            "active_plan_context": {"has_plan": False, "plan_details": None},
        }
    except Exception as e:
        logger.error(f"load_active_plan_state failed: {e}")
        return {
            "has_active_plan": False,
            "active_plan_id": None,
            "active_plan_context": {"has_plan": False, "plan_details": None},
        }


def _intake_summary(intake: Optional[IntakeAgentOutput]) -> Dict[str, Any]:
    """Return the minimal intake summary needed for supervisor routing."""

    return {
        "contract_ready": bool(intake and getattr(intake, "status", None) == "approved"),
    }


def _planner_summary(state: SupervisorState) -> Dict[str, Any]:
    """Return the minimal planner summary needed for supervisor routing."""

    committed = bool(state.get("committed"))
    verified_plan = state.get("verified_plan")
    draft_status = state.get("draft_status")

    return {
        "plan_verified": bool(verified_plan),
        "plan_committed": committed,
        "draft_status": (
            draft_status
            or ("committed" if committed else "awaiting_review" if verified_plan else "none")
        ),
    }


def _planner_mode_hint(state: SupervisorState) -> Optional[str]:
    """Return a supervisor-owned hint for the planner workflow mode."""

    explicit_hint = state.get("planner_mode_hint")
    if explicit_hint:
        return explicit_hint

    ui_action = state.get("ui_action") or {}
    if str(ui_action.get("id") or "").strip() == "approve_plan":
        return "approve"

    ui_context = state.get("ui_context") or {}
    if str(ui_context.get("source") or "").strip() == "pending_plan_review":
        return "revise"

    if state.get("has_active_plan"):
        return "revise"

    return "create"


def _build_router_runtime_state(state: SupervisorState) -> Dict[str, Any]:
    """Build the compact runtime JSON the supervisor router is allowed to see."""

    intake_summary = _intake_summary(state.get("intake"))
    planner_summary = _planner_summary(state)
    worker_envelope = state.get("worker_envelope")
    contract_ready = bool(state.get("contract_ready", intake_summary["contract_ready"]))

    return {
        "has_active_plan": state.get("has_active_plan", False),
        "contract_ready": contract_ready,
        "plan_verified": planner_summary["plan_verified"],
        "plan_committed": planner_summary["plan_committed"],
        "draft_status": planner_summary["draft_status"],
        "planner_mode_hint": _planner_mode_hint(state),
        "ui_context": state.get("ui_context"),
        "worker_envelope": (
            {
                "agent_name": worker_envelope.get("agent_name"),
                "message": worker_envelope.get("message"),
            }
            if worker_envelope
            else None
        ),
    }


def _latest_user_text(state: SupervisorState) -> str:
    """Return the latest human message text from supervisor state."""

    for message in reversed(state.get("messages", []) or []):
        if isinstance(message, HumanMessage):
            return str(message.content or "").strip()
    return ""


def _extract_planner_visible_text(messages: List[BaseMessage]) -> str:
    """Prefer the planner's actual user message over verifier boilerplate."""

    ignored_prefixes = (
        "The draft plan failed deterministic verification.",
        "Verifier did not receive an unverified plan to check.",
        "Plan passed deterministic verification and is ready for review.",
    )
    ai_texts: List[str] = []
    for message in messages:
        if not isinstance(message, AIMessage):
            continue
        text = str(message.content or "").strip()
        if text:
            ai_texts.append(text)

    for text in reversed(ai_texts):
        if not text.startswith(ignored_prefixes):
            return text
    return ai_texts[-1] if ai_texts else ""


def _build_plan_review_ui() -> Dict[str, Any]:
    """Build the structured popup payload for draft-plan review."""

    return {
        "type": "plan_review",
        "actions": list(PLAN_REVIEW_ACTIONS),
    }


async def check_plan_node(state: SupervisorState) -> dict:
    active_plan_state = await load_active_plan_state(state["user_id"])
    logger.info(
        "[CHECK_PLAN] has_active_plan=%s active_plan_id=%s",
        active_plan_state["has_active_plan"],
        active_plan_state["active_plan_id"],
    )

    return {
        **active_plan_state,
        "contract_ready": _intake_summary(state.get("intake")).get("contract_ready", False),
        "draft_status": _planner_summary(state).get("draft_status", "none"),
        "planner_mode_hint": _planner_mode_hint(state),
        "worker_envelope": None,
        "worker_outcome": None,
        "worker_hops_this_turn": 0,
        "final_reply": None,
    }


async def plan_action_node(state: SupervisorState) -> dict:
    """Handle structured UI plan actions without asking the router to guess intent."""

    ui_action = state.get("ui_action") or {}
    action_id = str(ui_action.get("id") or "").strip()
    if not action_id:
        return {"routing_decision": None}

    if action_id == "approve_plan":
        decision = RoutingDecision(
            intent="approve_plan",
            confidence=1.0,
            reasoning="The user explicitly approved the pending draft plan.",
            agent_chosen="planner",
        )
        return {
            "routing_decision": decision,
            "draft_status": "awaiting_review",
            "planner_mode_hint": "approve",
            "pending_ui": None,
            "ui_action": None,
        }

    if action_id == "cancel_plan":
        return {
            "routing_decision": RoutingDecision(
                intent="chat",
                confidence=1.0,
                reasoning="The user cancelled the pending draft plan review.",
                agent_chosen="user_facing",
            ),
            "planner_status": "cancelled",
            "draft_status": "cancelled",
            "planner_mode_hint": "revise",
            "verified_plan": None,
            "pending_ui": None,
            "ui_action": None,
            "worker_envelope": make_envelope(
                "planner", "cancelled",
                "Okay, I cancelled this draft plan. We can make a new one whenever you want.",
                data={"committed": False, "has_verified_plan": False},
            ),
        }

    if action_id == "request_changes":
        return {
            "routing_decision": RoutingDecision(
                intent="chat",
                confidence=1.0,
                reasoning="The user wants changes but has not specified which changes yet.",
                agent_chosen="user_facing",
            ),
            "draft_status": "awaiting_review",
            "planner_mode_hint": "revise",
            "pending_ui": None,
            "ui_action": None,
            "worker_envelope": make_envelope(
                "planner", "pending",
                "Tell me what you want changed in the draft plan, and I'll revise it.",
                data={"committed": False, "has_verified_plan": True},
            ),
        }

    return {
        "routing_decision": RoutingDecision(
            intent="chat",
            confidence=1.0,
            reasoning="The UI action was unknown, so the user should receive a safe fallback reply.",
            agent_chosen="user_facing",
        ),
        "pending_ui": None,
        "ui_action": None,
            "worker_envelope": make_envelope(
                "supervisor", "rejected",
                "I couldn't understand that plan action. Try again.",
                error=f"unknown_ui_action:{action_id}",
            ),
    }


async def supervisor_node(state: SupervisorState) -> dict:
    """
    Minimal structured router for the slop supervisor.
    """
    started_at = time.time()
    ui_context = state.get("ui_context") or {}
    if (
        state.get("draft_status") == "awaiting_review"
        and str(ui_context.get("source") or "").strip() == "pending_plan_review"
    ):
        return {
            "routing_decision": RoutingDecision(
                intent="update_plan",
                confidence=1.0,
                reasoning="The user submitted free-form feedback while reviewing a verified draft plan.",
                agent_chosen="planner",
            )
        }

    if state.get("worker_hops_this_turn", 0) >= 3:
        decision = RoutingDecision(
            intent="unknown",
            confidence=1.0,
            reasoning="The worker hop limit for this turn was reached, so the user should receive the latest result.",
            agent_chosen="user_facing",
        )
        logger.info("[SLOP ROUTER] worker hop limit reached agent=user_facing")
        return {"routing_decision": decision}

    try:
        from src.database.client_cache import get_llm

        llm = get_llm("gpt-5-mini", 0.0, reasoning_effort="minimal")
        router_llm = llm.with_structured_output(RoutingDecision)

        payload_started_at = time.time()
        runtime_state = _build_router_runtime_state(state)
        payload_finished_at = time.time()

        visible_messages = messages_with_summary(
            state.get("messages", []),
            state.get("conversation_summary"),
        )
        supervisor_messages = [
            SystemMessage(content=ROUTER_SYSTEM_PROMPT),
            *visible_messages,
            SystemMessage(content=f"Runtime state JSON:\n{runtime_state}"),
        ]

        llm_call_started_at = time.time()
        decision = await router_llm.ainvoke(supervisor_messages)
        llm_call_finished_at = time.time()

        finished_at = time.time()
        message_chars = sum(
            len(str(getattr(message, "content", "") or ""))
            for message in visible_messages
        )
        runtime_state_chars = len(str(runtime_state))
        worker_envelope_chars = len(str(state.get("worker_envelope"))) if state.get("worker_envelope") else 0

        logger.info(
            "[SLOP ROUTER TIMING] total_ms=%.2f payload_build_ms=%.2f llm_call_ms=%.2f "
            "post_llm_ms=%.2f message_count=%s message_chars=%s runtime_state_chars=%s worker_envelope_chars=%s",
            (finished_at - started_at) * 1000,
            (payload_finished_at - payload_started_at) * 1000,
            (llm_call_finished_at - llm_call_started_at) * 1000,
            (finished_at - llm_call_finished_at) * 1000,
            len(visible_messages),
            message_chars,
            runtime_state_chars,
            worker_envelope_chars,
        )

        logger.info(
            "[SLOP ROUTER] intent=%s confidence=%.2f agent=%s reason=%s",
            decision.intent,
            decision.confidence,
            decision.agent_chosen,
            decision.reasoning,
        )

        return {"routing_decision": decision}

    except Exception as e:
        logger.error(f"supervisor_node failed: {e}")
        fallback = RoutingDecision(
            intent="unknown",
            confidence=0.0,
            reasoning="Router failed, so defaulting to user-facing reply.",
            agent_chosen="user_facing",
        )
        return {"routing_decision": fallback}


def route_from_supervisor(state: SupervisorState) -> str:
    """Map the structured routing decision to the next graph node name."""

    routing_decision = state.get("routing_decision")
    if not routing_decision:
        return "user_facing_node"

    chosen = routing_decision.agent_chosen
    if chosen == "intake":
        return "intake_node"
    if chosen == "planner":
        return "planner_node"
    return "user_facing_node"



async def intake_node(state: SupervisorState) -> dict:
    """
    Run the state-driven Intake worker.

    The supervisor chooses ownership only. Intake decides how to maintain its
    contract from current contract and active-plan truth, without an action mode.
    """
    try:
        llm = get_llm("gpt-5-mini", 0.3, reasoning_effort="low")

        intake_agent = IntakeAgent(llm_client=llm, vector_store=VectorStore())
        app = intake_agent.intake_agent()
        active_plan_context = state.get("active_plan_context")
        if state.get("has_active_plan") and active_plan_context is None:
            from src.services.active_plan import get_active_plan_snapshot

            active_plan_started_at = time.perf_counter()
            active_plan_context = get_active_plan_snapshot(state["user_id"])
            logger.info(
                "[PERF][SUPERVISOR->INTAKE] preload_active_plan_snapshot duration_ms=%s has_plan=%s",
                round((time.perf_counter() - active_plan_started_at) * 1000, 2),
                bool(isinstance(active_plan_context, dict) and active_plan_context.get("has_plan")),
            )

        result = await app.ainvoke(
            {
                "messages": messages_with_summary(
                    state["messages"],
                    state.get("conversation_summary"),
                ),
                "user_id": state["user_id"],
                "intake": state.get("intake"),
                "user_context": state.get("user_context", ""),
                "calendar_blocks": (state.get("scheduling_context") or {}).get("calendar_blocks"),
                # Supervisor owns the worker handoff truth. Intake should
                # receive either a no-plan sentinel or the hydrated snapshot.
                "active_plan_context": active_plan_context,
                "scheduling_context": state.get("scheduling_context"),
                "turn_count": 0,
            }
        )

        intake_obj = result.get("intake")
        intake_ready = bool(
            intake_obj and getattr(intake_obj, "status", None) == "approved"
        )

        output_text = extract_worker_reply_text(result.get("messages", []))
        intake_status = getattr(intake_obj, "status", None) if intake_obj else None
        if intake_ready:
            worker_outcome: WorkerOutcome = {
                "worker": "intake",
                "outcome": "handoff",
                "next_worker": "planner",
            }
        elif intake_status == "rejected":
            worker_outcome = {
                "worker": "intake",
                "outcome": "failed",
                "next_worker": None,
            }
        else:
            worker_outcome = {
                "worker": "intake",
                "outcome": "needs_user_input",
                "next_worker": None,
            }

        return {
            "messages": [],
            "intake": intake_obj,
            "contract_ready": intake_ready,
            "active_plan_context": active_plan_context,
            "scheduling_context": result.get("scheduling_context"),
            "verified_plan": None,
            "draft_status": "none",
            "planner_mode_hint": "create" if not state.get("has_active_plan") else "revise",
            "pending_ui": None,
            "worker_hops_this_turn": state.get("worker_hops_this_turn", 0) + 1,
            "worker_outcome": worker_outcome,
            "worker_envelope": make_envelope(
                "intake",
                getattr(intake_obj, "status", "rejected") if intake_obj else "rejected",
                output_text or "Intake processed the request.",
                data={
                    "intake_ready": intake_ready,
                },
            ),
        }

    except Exception as e:
        logger.error(f"intake_node failed: {e}")
        msg = (
            "I hit a snag while working on the intake. "
            "Tell me again what changed or what plan you want."
        )
        return {
            "messages": [],
            "contract_ready": False,
            "pending_ui": None,
            "worker_hops_this_turn": state.get("worker_hops_this_turn", 0) + 1,
            "worker_outcome": {
                "worker": "intake",
                "outcome": "failed",
                "next_worker": None,
            },
            "worker_envelope": make_envelope(
                "intake", "rejected", msg,
                data={"intake_ready": False},
                error=str(e),
            ),
        }


def route_after_intake(state: SupervisorState) -> str:
    """Apply the supervisor's deterministic policy to an Intake result."""

    outcome = state.get("worker_outcome") or {}
    if outcome.get("outcome") == "handoff" and outcome.get("next_worker") == "planner":
        logger.info("[SLOP ROUTER] deterministic intake outcome=handoff next=planner")
        return "planner_node"

    logger.info(
        "[SLOP ROUTER] deterministic intake outcome=%s next=user_facing",
        outcome.get("outcome", "failed"),
    )
    return "user_facing_node"


def _planner_commit_requested(state: SupervisorState) -> bool:
    """Return whether the supervisor is sending an explicit plan approval."""

    routing_decision = state.get("routing_decision")
    return getattr(routing_decision, "intent", None) == "approve_plan"


def _build_planner_request(state: SupervisorState) -> Dict[str, Any]:
    """Build the planner input packet from supervisor-owned truth."""

    return {
        "user_id": state["user_id"],
        "intake": state.get("intake"),
        "scheduling_context": state.get("scheduling_context"),
        "active_plan_context": state.get("active_plan_context"),
    }


async def planner_node(state: SupervisorState) -> dict:
    """Run the planner from the intake handoff state."""

    try:
        from src.agents.planner_agent import create_planner_graph, planner_state_from_input
        active_plan_context = state.get("active_plan_context")
        if state.get("has_active_plan") and active_plan_context is None:
            from src.services.active_plan import get_active_plan_snapshot

            active_plan_started_at = time.perf_counter()
            active_plan_context = get_active_plan_snapshot(state["user_id"])
            logger.info(
                "[PERF][SUPERVISOR->PLANNER] preload_active_plan_snapshot duration_ms=%s has_plan=%s",
                round((time.perf_counter() - active_plan_started_at) * 1000, 2),
                bool(isinstance(active_plan_context, dict) and active_plan_context.get("has_plan")),
            )

        intake_obj = state.get("intake")
        if not intake_obj:
            msg = "Planner needs intake output before it can build the plan."
            return {
                "messages": [],
                "pending_ui": None,
                "worker_hops_this_turn": state.get("worker_hops_this_turn", 0) + 1,
            "worker_envelope": make_envelope(
                "planner", "rejected", msg,
                data={"planner_status": None},
                error="missing_intake",
            ),
            }

        intake_status = getattr(intake_obj, "status", None)
        if intake_status != "approved":
            msg = "The intake is not ready for planning yet."
            return {
                "messages": [],
                "pending_ui": None,
                "worker_hops_this_turn": state.get("worker_hops_this_turn", 0) + 1,
            "worker_envelope": make_envelope(
                "planner", "rejected", msg,
                data={"planner_status": None},
                error=f"intake_not_ready:{intake_status}",
            ),
            }

        existing_verified_plan = state.get("verified_plan")

        # Planner has one normal work path plus one explicit commit path.
        commit_requested = _planner_commit_requested(state)
        if commit_requested:
            if not existing_verified_plan:
                msg = "There is no verified draft plan to approve right now."
                return {
                    "messages": [],
                    "pending_ui": None,
                    "worker_hops_this_turn": state.get("worker_hops_this_turn", 0) + 1,
                    "worker_envelope": make_envelope(
                        "planner", "rejected", msg,
                        data={"planner_status": "rejected"},
                        error="missing_verified_plan_for_approval",
                    ),
                }

        planner_input = _build_planner_request(state)

        planner_state = planner_state_from_input(
            planner_input,
            commit_requested=commit_requested,
            messages=messages_with_summary(
                state["messages"],
                state.get("conversation_summary"),
            ),
            user_context=state.get("user_context", ""),
            verified_plan=existing_verified_plan,
            has_active_plan=state.get("has_active_plan", False),
            active_plan_id=state.get("active_plan_id"),
        )

        result = await asyncio.wait_for(
            create_planner_graph(user_context=state.get("user_context", "")).ainvoke(planner_state),
            timeout=120.0,
        )

        output_text = _extract_planner_visible_text(result.get("messages", []))

        committed = bool(result.get("committed"))
        has_reviewable_plan = bool(result.get("verified_plan"))
        planner_status = result.get("planner_status")
        if planner_status not in {
            "pending",
            "needs_input",
            "awaiting_approval",
            "rejected",
            "committed",
            "escalate",
        }:
            if committed:
                planner_status = "committed"
            elif has_reviewable_plan:
                planner_status = "awaiting_approval"
            else:
                planner_status = "pending"

        return {
            "messages": [],
            "planner_status": planner_status,
            "active_plan_context": active_plan_context,
            "verified_plan": result["verified_plan"].model_dump() if result.get("verified_plan") else None,
            "committed": committed,
            "draft_status": (
                "committed"
                if committed
                else "awaiting_review"
                if planner_status == "awaiting_approval"
                else "rejected"
                if planner_status == "rejected"
                else "none"
            ),
            "planner_mode_hint": "approve" if commit_requested else ("revise" if state.get("has_active_plan") else "create"),
            "pending_ui": _build_plan_review_ui() if planner_status == "awaiting_approval" else None,
            "ui_action": None,
            "worker_hops_this_turn": state.get("worker_hops_this_turn", 0) + 1,
            "worker_envelope": make_envelope(
                "planner",
                planner_status,
                output_text or "Planner finished processing.",
                data={
                    "planner_status": planner_status,
                    "committed": committed,
                    "has_verified_plan": has_reviewable_plan,
                },
            ),
        }

    except asyncio.TimeoutError:
        msg = "Planning took too long. Try again."
        return {
            "messages": [],
            "draft_status": "rejected",
            "pending_ui": None,
            "worker_hops_this_turn": state.get("worker_hops_this_turn", 0) + 1,
            "worker_envelope": make_envelope(
                "planner", "rejected", msg,
                data={"planner_status": None},
                error="timeout_120s",
            ),
        }

    except Exception as e:
        logger.error(f"planner_node failed: {e}")
        msg = "Had trouble building the plan. Want to try again?"
        return {
            "messages": [],
            "draft_status": "rejected",
            "pending_ui": None,
            "worker_hops_this_turn": state.get("worker_hops_this_turn", 0) + 1,
            "worker_envelope": make_envelope(
                "planner", "rejected", msg,
                data={"planner_status": None},
                error=str(e),
            ),
        }


async def user_facing_node(state: SupervisorState) -> dict:
    """Synthesize the current turn's worker outputs into the final assistant reply."""

    writer = get_writer_or_none()
    worker_envelope = state.get("worker_envelope")
    if not worker_envelope:
        try:
            llm = get_llm("gpt-5-mini", 0.3)
            msg = await stream_llm_text(
                llm,
                [
                    SystemMessage(
                        content=(
                            "You are SkedioAI, a concise Class 10 study assistant. "
                            "Answer naturally and helpfully. "
                        )
                    ),
                    *messages_with_summary(
                        state["messages"],
                        state.get("conversation_summary"),
                    ),
                ],
                writer,
            )
            if not msg:
                msg = "I'm here."
        except Exception as exc:
            logger.warning("user_facing fallback LLM failed: %s", exc)
            msg = "Hey! How can I help you with your study plan?"
            await stream_plain_text(msg, writer)
        return {
            "messages": [AIMessage(content=msg)],
            "final_reply": msg,
            "worker_envelope": None,
        }

    final_reply = str(worker_envelope.get("message") or "").strip()
    if final_reply:
        final_reply = await stream_plain_text(final_reply, writer)
        return {
            "messages": [AIMessage(content=final_reply)],
            "final_reply": final_reply,
            "worker_envelope": None,
        }

    try:
        llm = get_llm("gpt-5-mini", 0.2)
        worker_json = json.dumps(worker_envelope, default=str, ensure_ascii=False)
        final_reply = await stream_llm_text(
            llm,
            [
                SystemMessage(
                    content=(
                        "You are SkedioAI's final renderer. "
                        "You receive one turn's worker envelope. "
                        "Your job is to make the worker's existing message user-facing, "
                        "clear, and lightly formatted. "
                        "Preserve the worker's meaning. "
                        "Do not mention internal routing or system state."
                    )
                ),
                SystemMessage(content=f"Worker envelope for this turn:\n{worker_json}"),
            ],
            writer,
        )
    except Exception as exc:
        logger.warning("user_facing envelope renderer failed: %s", exc)
        final_reply = ""

    if not final_reply:
        final_reply = str(worker_envelope.get("message") or "Done.")
        final_reply = await stream_plain_text(final_reply, writer)

    return {
        "messages": [AIMessage(content=final_reply)],
        "final_reply": final_reply,
        "worker_envelope": None,
    }


def create_supervisor_graph(checkpointer: Optional[MemorySaver] = None):
    """Build the minimal slop supervisor graph."""

    workflow = StateGraph(SupervisorState)

    workflow.add_node("compress_history_node", compress_history_node)
    workflow.add_node("check_plan_node", check_plan_node)
    workflow.add_node("plan_action_node", plan_action_node)
    workflow.add_node("supervisor_node", supervisor_node)
    workflow.add_node("intake_node", intake_node)
    workflow.add_node("planner_node", planner_node)
    workflow.add_node("user_facing_node", user_facing_node)

    workflow.add_edge(START, "compress_history_node")
    workflow.add_edge("compress_history_node", "check_plan_node")
    workflow.add_conditional_edges(
        "check_plan_node",
        lambda state: "plan_action_node" if state.get("ui_action") else "supervisor_node",
        {
            "plan_action_node": "plan_action_node",
            "supervisor_node": "supervisor_node",
        },
    )
    workflow.add_conditional_edges(
        "plan_action_node",
        route_from_supervisor,
        {
            "intake_node": "intake_node",
            "planner_node": "planner_node",
            "user_facing_node": "user_facing_node",
        },
    )
    workflow.add_conditional_edges(
        "supervisor_node",
        route_from_supervisor,
        {
            "intake_node": "intake_node",
            "planner_node": "planner_node",
            "user_facing_node": "user_facing_node",
        },
    )

    workflow.add_conditional_edges(
        "intake_node",
        route_after_intake,
        {
            "planner_node": "planner_node",
            "user_facing_node": "user_facing_node",
        },
    )
    workflow.add_edge("planner_node", "supervisor_node")
    workflow.add_edge("user_facing_node", END)

    return workflow.compile(checkpointer=checkpointer) if checkpointer else workflow.compile()


# ---------------------------------------------------------------------------
# CLI Harness
# ---------------------------------------------------------------------------

async def run_interactive_session(user_id: str = "test_user_91212219"):
    """Run a local terminal session for manual Supervisor testing."""

    import uuid

    session_id = str(uuid.uuid4())[:8]
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"convo_supervisor_{session_id}.log")

    turn_count = 0

    def serialize_message(message) -> dict:
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

    def write_log(event_type: str, content) -> None:
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
        "has_active_plan": False,
        "active_plan_id": None,
        "active_plan_context": {"has_plan": False, "plan_details": None},
        "contract_ready": False,
        "draft_status": "none",
        "planner_mode_hint": None,
        "routing_decision": None,
        "intake": None,
        "scheduling_context": None,
        "planner_status": None,
        "verified_plan": None,
        "committed": False,
        "pending_ui": None,
        "ui_action": None,
        "worker_envelope": None,
        "worker_hops_this_turn": 0,
        "final_reply": None,
    }

    app = None
    print("SkedioAI Supervisor started. Type 'exit' to stop.\n")
    print(f"Palantir Supervisor Logging Enabled: {log_file}\n")
    write_log(
        "SYSTEM_START",
        {
            "user_id": user_id,
            "model": "gpt-5-mini",
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
                app = create_supervisor_graph()

            result = None
            streamed_reply = ""
            started_stream = False
            async for mode, data in app.astream(
                state,
                stream_mode=["custom", "values"],
            ):
                if mode == "custom":
                    if not isinstance(data, dict):
                        continue
                    if data.get("event") != "user_facing_chunk":
                        continue
                    text = str(data.get("text") or "")
                    if not text:
                        continue
                    if not started_stream:
                        print("\nSkedioAI: ", end="", flush=True)
                        started_stream = True
                    print(text, end="", flush=True)
                    streamed_reply += text
                    continue

                if mode == "values":
                    result = data

            if started_stream:
                print("\n")

            if result is None:
                raise RuntimeError("Supervisor graph returned no final state.")

            # --- compute timing ---
            elapsed = time.time() - turn_started_at
            new_messages = result["messages"][old_message_count:]

            # --- extract assistant text for display ---
            assistant_reply = streamed_reply.strip()
            if not assistant_reply:
                for msg in reversed(new_messages):
                    if getattr(msg, "tool_calls", None):
                        continue
                    text = getattr(msg, "content", "")
                    if text:
                        assistant_reply = text
                        break

            # --- log everything ---
            write_log(
                "ASSISTANT_MESSAGES",
                [serialize_message(m) for m in new_messages],
            )

            # --- log routing + sub-agent output ---
            routing = result.get("routing_decision")
            if routing:
                write_log("ROUTING_DECISION", routing)

            intake = result.get("intake")
            if intake:
                write_log("INTAKE_RESULT", intake)

            verified_plan = result.get("verified_plan")
            if verified_plan:
                write_log("VERIFIED_PLAN", verified_plan)

            if result.get("committed"):
                write_log("PLAN_COMMITTED", True)

            worker_envelope = result.get("worker_envelope")
            if worker_envelope:
                write_log("WORKER_ENVELOPE", worker_envelope)

            write_log(
                "TURN_SUMMARY",
                {
                    "elapsed_seconds": round(elapsed, 2),
                    "messages_added": len(new_messages),
                    "final_reply_length": len(assistant_reply),
                },
            )

            # --- print to terminal ---
            if not streamed_reply:
                print(f"\nSkedioAI: {assistant_reply}\n")

            # --- mutate state for next turn ---
            state = result

        except Exception as exc:
            import traceback

            elapsed = time.time() - turn_started_at
            tb = traceback.format_exc()
            write_log(
                "ERROR",
                {
                    "error": str(exc),
                    "traceback": tb,
                    "elapsed_seconds": round(elapsed, 2),
                },
            )
            print(f"\n[ERROR] {exc}\n")

    write_log("SYSTEM_STOP", {"total_turns": turn_count})
    print(f"\nSession log: {log_file}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run the SkedioAI Supervisor agent interactively.")
    parser.add_argument("--user-id", default="test_user_9922312313", help="User ID for the session.")
    args = parser.parse_args()

    asyncio.run(run_interactive_session(user_id=args.user_id))
