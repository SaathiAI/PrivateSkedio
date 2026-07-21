# Supervisor Routing Diagram

This document maps `src/agents/supervisor_slop.py` as it exists now.

It is the live truth for:
- routing
- worker handoff
- review-state handling
- user-facing rendering after worker execution

Despite the filename, the runtime pattern is fairly disciplined:
- one supervisor
- one intake worker
- one planner worker
- one user-facing renderer

The supervisor is not a planner and not an intake fallback brain.
Its job is to decide who owns the next move.

## High-Level Flow

```mermaid
flowchart TD
    CheckPlan --> DecideAction{"ui_action present?"}
    DecideAction -->|yes| PlanAction["plan_action_node"]
    DecideAction -->|no| Supervisor["supervisor_node"]

    PlanAction --> RouteA{"route_from_supervisor"}
    Supervisor --> RouteB{"route_from_supervisor"}

    RouteA -->|planner| Planner["planner_node"]
    RouteA -->|user_facing| UserFacing["user_facing_node"]

    RouteB -->|intake| Intake["intake_node"]
    RouteB -->|planner| Planner
    RouteB -->|user_facing| UserFacing

    Intake --> Supervisor
    Planner --> PlannerRoute{"route_after_planner"}
    PlannerRoute -->|display-ready outcome| UserFacing
    PlannerRoute -->|needs more routing| Supervisor
    UserFacing --> End["END"]
```

## Ownership Boundary

```mermaid
flowchart LR
    Supervisor["Supervisor"]
    Intake["Intake worker"]
    Planner["Planner worker"]
    UserFacing["User-facing node"]

    Supervisor --> Intake
    Supervisor --> Planner
    Supervisor --> UserFacing

    State["Shared state"] --> Supervisor
    Envelope["worker_envelope"] --> Supervisor
    Messages["clean visible messages"] --> Supervisor
```

Supervisor owns:
- routing
- worker handoff
- `pending_ui`
- structured UI actions
- review-action interpretation
- turn-level worker result storage through `worker_envelope`

Supervisor does not own:
- intake contract generation
- plan drafting
- verification
- commit
- rewriting worker ownership boundaries on the fly

## Current State Shape

```mermaid
flowchart TB
    State["SupervisorState"]

    State --> Messages["messages"]
    State --> UserId["user_id"]
    State --> HasPlan["has_active_plan"]
    State --> PlanId["active_plan_id"]
    State --> PlanContext["active_plan_context"]
    State --> Intake["intake"]
    State --> Scheduling["scheduling_context"]
    State --> PlannerStatus["planner_status"]
    State --> Verified["verified_plan"]
    State --> Committed["committed"]
    State --> PendingUI["pending_ui"]
    State --> UIAction["ui_action"]
    State --> Envelope["worker_envelope"]
    State --> Outcome["worker_outcome"]
    State --> Hops["worker_hops_this_turn"]
    State --> FinalReply["final_reply"]
```

## `check_plan_node`

```mermaid
flowchart TD
    Node["check_plan_node"] --> GetPlan["get_active_plan_status(user_id)"]
    GetPlan --> HasPlan{"has active plan?"}
    HasPlan -->|yes| ReturnPlan["set has_active_plan + active_plan_id"]
    HasPlan -->|no| ReturnNone["set has_active_plan false + no-plan sentinel"]
    ReturnPlan --> Reset["clear worker_envelope and reset worker_hops_this_turn"]
    ReturnNone --> Reset
```

## `plan_action_node`

```mermaid
flowchart TD
    Action["ui_action.id"] --> Choice{"action id"}
    Choice -->|approve_plan| Approve["intent=approve_plan -> planner"]
    Choice -->|request_changes| Changes["show ask-for-changes message via user_facing"]
    Choice -->|cancel_plan| Cancel["clear review state and show cancelled message"]
    Choice -->|unknown| Unknown["safe fallback to user_facing"]
```

## `supervisor_node`

```mermaid
flowchart TD
    StartNode["supervisor_node"] --> HopCheck{"worker_hops_this_turn >= 3?"}
    HopCheck -->|yes| ForceUF["route to user_facing"]
    HopCheck -->|no| Runtime["build compact runtime_state"]
    Runtime --> Prompt["ROUTER_SYSTEM_PROMPT + messages + runtime state"]
    Prompt --> LLM["gpt-5-mini structured RoutingDecision"]
    LLM --> Decision["routing_decision"]
```

The router sees:
- clean visible `messages`
- `contract_ready`
- `plan_verified`
- `plan_committed`
- latest `worker_envelope`

Current routing ideology:
- `has_active_plan` is context, not the main decider
- user intent drives the next worker
- worker ownership decides whether intake or planner should act
- the supervisor should prefer explicit state over conversational guesswork

## `intake_node`

```mermaid
flowchart TD
    IntakeNode["intake_node"] --> State["pass current intake + active-plan truth"]
    State --> RunIntake["run state-driven IntakeAgent graph"]
    RunIntake --> Extract["extract intake + scheduling_context + visible reply"]
    Extract --> Envelope["build intake worker_envelope"]
    Envelope --> Return["store intake, scheduling_context, worker_envelope"]
```

The supervisor no longer chooses an Intake action/mode. For users without an
active plan it passes the already-known no-plan result, avoiding a duplicate
lookup. For active-plan users, Intake loads the complete progress snapshot it
needs to maintain the contract.

## `planner_node`

```mermaid
flowchart TD
    PlannerNode["planner_node"] --> HaveIntake{"approved intake exists?"}
    HaveIntake -->|no| Reject["return rejected planner envelope"]
    HaveIntake -->|yes| Handoff["build planner request from supervisor truth"]
    Handoff --> Intent{"approve_plan intent?"}
    Intent -->|yes| CommitAction["commit_requested = true"]
    Intent -->|no| NormalWork["commit_requested = false"]
    CommitAction --> RunGraph["run planner graph"]
    NormalWork --> RunGraph
    RunGraph --> Extract["read planner_status, verified_plan, committed"]
    Extract --> PendingUI{"planner_status == awaiting_approval?"}
    PendingUI -->|yes| BuildUI["build pending_ui"]
    PendingUI -->|no| SkipUI["pending_ui = null"]
    BuildUI --> PlannerEnvelope["return planner worker_envelope"]
    SkipUI --> PlannerEnvelope
```

Rule:
- commit is the only explicit planner command
- `has_active_plan` provides the create-vs-revise runtime truth
- `awaiting_approval`, `committed`, `needs_input`, `rejected`, and `escalate`
  route directly to `user_facing_node` after Planner
- a verified draft created in this turn is shown before any approval decision is
  made in a later turn

This is the important product behavior:

```text
draft now
review now
approve later
commit later
```

## `user_facing_node`

```mermaid
flowchart TD
    UserFacingNode["user_facing_node"] --> HasEnvelope{"worker_envelope exists?"}
    HasEnvelope -->|no| ChatReply["answer from clean chat history"]
    HasEnvelope -->|yes| HasMessage{"worker_envelope.message exists?"}
    HasMessage -->|yes| Direct["stream message directly"]
    HasMessage -->|no| Render["lightly render envelope with LLM"]
    ChatReply --> Return["append final AI message and clear worker_envelope"]
    Direct --> Return
    Render --> Return
```

## Review UI Path

```mermaid
flowchart TD
    Verified["planner_status = awaiting_approval"] --> UI["pending_ui plan_review payload"]
    UI --> Display["user_facing displays planner envelope + draft controls"]
    Display --> EndTurn["END current turn"]
    EndTurn --> NextTurn["later user action/message"]
    NextTurn --> UserChoice{"user reviews"}
    UserChoice -->|approve_plan| Commit["plan_action_node -> planner commit"]
    UserChoice -->|request_changes| Ask["plan_action_node -> user_facing asks for change details"]
    UserChoice -->|cancel_plan| Cancel["plan_action_node clears review state"]
```

## Envelope Contract

```mermaid
flowchart TB
    Envelope["AgentOutputEnvelope"]
    Envelope --> Id["id"]
    Envelope --> Agent["agent_name"]
    Envelope --> Status["status"]
    Envelope --> Message["message"]
    Envelope --> Data["data"]
    Envelope --> Error["error"]
    Envelope --> Created["created_at"]
```

The supervisor routes from:
- shared state
- `worker_envelope`
- clean `messages`

Not from raw worker tool transcripts.

## Practical Summary

If you want one sentence for the whole file, use this:

```text
Supervisor decides the owner of the next turn, then gets out of the way.
```

That keeps the system from collapsing into one overpowered router prompt that
tries to think, validate, schedule, and render all at once.
