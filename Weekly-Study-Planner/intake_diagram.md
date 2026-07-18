# Intake Agent Diagram

This document maps `src/agents/intake_agent.py` as it exists now.

## High-Level Intake Loop

```mermaid
flowchart TD
    Start["START"] --> Agent["call_agent"]
    Agent --> RouteAgent{"route_after_agent"}
    RouteAgent -->|tool calls present| Tools["call_tools"]
    RouteAgent -->|approved intake ready| End1["END"]
    RouteAgent -->|no tool calls| End2["END"]

    Tools --> RouteTools{"route_after_tools"}
    RouteTools -->|approved intake ready| End3["END"]
    RouteTools -->|plain AI reply| End4["END"]
    RouteTools -->|turn_count >= 18| End5["END"]
    RouteTools -->|otherwise| Agent
```

## Ownership Boundary

```mermaid
flowchart TD
    User["User"] --> Supervisor["Supervisor"]
    Supervisor --> Intake["Intake worker"]
    Intake --> Supervisor

    Intake --> Goal["goal"]
    Intake --> Availability["availability"]
    Intake --> StudyItems["study_items"]
    Intake --> Scheduling["scheduling_context"]
```

Intake owns:
- contract facts
- evidence gathering
- validation handoff
- planner-ready intake output

Intake does not own:
- timed session drafting
- schedule placement
- plan commit

## Live Status Values

```mermaid
flowchart LR
    Pending["pending"] --> Approved["approved"]
    Pending --> Rejected["rejected"]
```

Current meanings:
- `pending`
  - still collecting or repairing facts
- `approved`
  - planner handoff is ready
- `rejected`
  - current request could not be accepted as-is

## Current Inputs

```mermaid
flowchart TB
    State["IntakeState"]
    State --> Messages["messages"]
    State --> UserId["user_id"]
    State --> Intake["intake"]
    State --> UserContext["user_context"]
    State --> ActivePlan["active_plan_context"]
    State --> Scheduling["scheduling_context"]
    State --> CalendarBlocks["calendar_blocks"]
    State --> Feasibility["feasibility_result"]
    State --> TurnCount["turn_count"]
```

`IntakeState` no longer contains an action/mode field. Runtime truth determines
whether Intake is forming a first contract or maintaining the contract behind
an active plan.

## `call_agent`

```mermaid
flowchart TD
    CallAgent["call_agent"] --> Build["build_agent_invocation"]
    Build --> PlanTruth["read supervisor-provided active_plan_context"]
    PlanTruth --> Prompt["build intake_agent_prompt"]
    Prompt --> Context{"active plan exists?"}
    Context -->|no| PlainMsgs["system prompt + chat history"]
    Context -->|yes| PlanMsgs["system prompt + chat history + active-plan context"]
    PlainMsgs --> SharedLLM["one bound Intake LLM"]
    PlanMsgs --> SharedLLM
    SharedLLM --> Response["AI response with at least one tool call"]
```

Current prompt boundary:

```text
There is now one canonical runtime prompt vessel:
`intake_agent_prompt`.

Active-plan truth changes the extra runtime context sent to Intake, not which
runtime prompt file gets selected. Intake no longer does a hidden fallback
`get_active_plan` fetch inside the agent invocation path.
```

`tool_choice="required"` requires at least one tool call. Evidence tools may run
first; the graph loops back so `commit_intake` can checkpoint the contract.

## `call_tools`

```mermaid
flowchart TD
    CallTools["call_tools"] --> ToolCalls["read latest tool calls"]
    ToolCalls --> CommitCheck{"contains commit_intake?"}
    CommitCheck -->|no| Evidence["run evidence tools in parallel"]
    CommitCheck -->|yes, mixed batch| Defer["run evidence + defer commit"]
    CommitCheck -->|yes, commit only| Sanitize["sanitize_commit_payload"]
    Sanitize --> Validate["validate_intake_contract"]
    Evidence --> ToolMsgs["return ToolMessage results"]
    Defer --> ToolMsgs
    Validate --> Accepted{"accepted?"}
    Accepted -->|yes| Save["store clean intake + scheduling_context"]
    Accepted -->|no| Repair["return validation feedback and keep loop going"]
```

The validator is the state authority, not raw model prose.

## Tool Categories

```mermaid
flowchart LR
    IntakeTools["one Intake tool registry"] --> Backlog["query_backlog"]
    IntakeTools --> Calendar["get_calendar_availability"]
    IntakeTools --> Syllabus["query_syllabus"]
    IntakeTools --> Verify["verify_claim_search"]
    IntakeTools --> Update["update_syllabus_entry"]
    IntakeTools --> Commit["commit_intake"]
```

Current live intake tools are:
- `query_backlog`
- `get_calendar_availability`
- `query_syllabus`
- `verify_claim_search`
- `update_syllabus_entry`
- `commit_intake`

Important rule:

```text
Intake owns contract evidence and contract acceptance.
It does not reach for old planner-side helper tools to imitate scheduling.
```

## Output Shape

```mermaid
flowchart TB
    Output["IntakeAgentOutput"]
    Output --> Status["status"]
    Output --> Message["message"]
    Output --> Goal["goal"]
    Output --> Availability["availability"]
    Output --> StudyItems["study_items"]
```

Planner handoff requires:
- `status = approved`
- valid `goal`
- valid `availability`
- valid `study_items`

## Supervisor Handoff

```mermaid
flowchart TD
    IntakeApproved["approved intake"] --> SupervisorState["supervisor state"]
    SupervisorState --> IntakeField["intake"]
    SupervisorState --> SchedulingField["scheduling_context"]
    SupervisorState --> Envelope["worker_envelope"]
    Envelope --> Planner["planner_node can now run"]
```

That is the current handoff contract between intake and planner.
Intake approval can hand the same work forward to Planner, but it does not mean
the final study plan is approved. Planner still drafts, verifies, and sends the
draft to user-facing review before any later commit.
