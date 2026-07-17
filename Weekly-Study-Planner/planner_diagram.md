# Planner Agent Diagram

This document maps the current live planner architecture.

The main live simplification is:
- one Planner agent owns both first-time plan creation and later schedule revision
- Intake owns contract facts
- Planner owns schedule creation and schedule revision
- verify and commit stay deterministic around Planner

## High-Level Flow

```mermaid
flowchart TD
    Start["START"] --> Planner["planner_node"]
    Planner --> HasDraft{"draft plan returned?"}
    HasDraft -->|no| End1["END"]
    HasDraft -->|yes| Verify["verify_node"]
    Verify --> Passed{"verified?"}
    Passed -->|no| Retry{"retry budget left?"}
    Retry -->|yes| Planner
    Retry -->|no| End2["END"]
    Passed -->|yes| Await["awaiting_approval"]
    Await --> End3["END"]

    CommitTrigger["approve_plan from user"] --> Commit["commit_node"]
    Commit --> End4["END"]
```

The practical interpretation is:

- planner drafts a schedule
- deterministic verification checks it
- frontend previews it
- user approval decides whether commit happens

That preview step is important.
The planner is not directly mutating the durable active plan on first output.

## Ownership Boundary

```mermaid
flowchart LR
    Intake["Intake"] -->|locked contract| Planner["Planner"]
    UserFeedback["User schedule feedback"] --> Planner
    Planner --> Draft["draft schedule"]
    Draft --> Verify["deterministic verifier"]
    Verify --> Approved["verified draft"]
    Approved --> UI["user review"]
    UI --> Commit["commit"]
```

Planner owns:
- making the first usable schedule
- revising an existing schedule
- handling schedule-shape feedback
- preparing a draft for verification
- staying inside schedule ownership instead of re-opening contract questions by itself

Planner does not own:
- collecting core contract facts
- changing subjects, scope, deadline, or feasibility rules by itself
- final UI messaging

## Mental Model

```mermaid
flowchart TB
    Contract["Study contract from Intake"] --> PlannerBrain["One Planner brain"]
    ExistingPlan["Current active plan if any"] --> PlannerBrain
    UserRequest["Latest user request"] --> PlannerBrain
    Calendar["Calendar constraints"] --> PlannerBrain
    PlannerBrain --> DraftPlan["Draft plan"]
    DraftPlan --> Verify["Verify"]
    Verify --> Commit["Commit later if approved"]
```

The Planner decides like this:
- no active plan yet -> create the first schedule
- active plan exists + user wants timing/workload changes -> revise that schedule
- active plan exists + user request changes contract facts -> hand off back to Intake

That split is one of the most important live product boundaries.

## Planner State

```mermaid
flowchart TB
    State["PlannerState"]
    State --> Request["request"]
    State --> CommitReq["commit_requested"]
    State --> Messages["messages"]
    State --> UserContext["user_context"]
    State --> HasPlan["has_active_plan"]
    State --> PlanId["active_plan_id"]
    State --> Draft["unverified_plan"]
    State --> Verified["verified_plan"]
    State --> Status["planner_status"]
    State --> Errors["verify_errors"]
    State --> Attempts["verify_attempts"]
    State --> Committed["committed"]
```

The live simplification is:
- no split planner personalities in the state
- commit is the only explicit special command
- runtime truth decides whether planner is creating or revising

## Planner Entry Logic

```mermaid
flowchart TD
    Entry["planner graph starts"] --> CommitCheck{"commit_requested?"}
    CommitCheck -->|yes| Commit["commit_node"]
    CommitCheck -->|no| CheckPlan{"active plan exists?"}
    CheckPlan -->|no| CreateContext["build create-mode context"]
    CheckPlan -->|yes| ReviseContext["build revise-mode context"]
    CreateContext --> Shared["one planner worker invocation"]
    ReviseContext --> Shared
    Shared --> Output["PlannerOutput"]
```

Important idea:

```text
one normal planner code path
+ different runtime context
+ same ownership boundary
+ one explicit commit path
```

This keeps the system easier to reason about than a pile of planner sub-agents with overlapping jobs.

## Planner Node

```mermaid
flowchart TD
    PlannerNode["planner_node"] --> Build["build planner invocation"]
    Build --> Prompt["planner prompt"]
    Prompt --> Tools["planner tools available"]
    Tools --> Model["one Planner LLM path"]
    Model --> Parse["parse PlannerOutput"]
    Parse --> DraftCheck{"plan present?"}
    DraftCheck -->|yes| Fill["fill computed fields"]
    DraftCheck -->|no| Return["return status + message"]
    Fill --> Return
```

The live behavior is:
- one planner invocation path
- one planner tool boundary
- one visible planner output contract
- one draft object the frontend can preview before approval

## Tool Boundary

```mermaid
flowchart LR
    PlannerTools["Planner grounding tools"] --> Backlog["query_backlog"]
    PlannerTools --> Syllabus["query_syllabus"]
    Approval["explicit user approval"] --> Commit["commit_plan code path"]
```

Typical usage:
- `query_backlog`
  - only when the locked contract lacks enough learner-progress detail for concrete session content
- `query_syllabus`
  - when official topic names, removed topics, active topics, or weightage matter
- commit path
  - only after explicit user approval and deterministic verification

Calendar truth is passed in planner context.
Planner should not fetch calendar data during normal draft generation.

## Verification Path

```mermaid
flowchart TD
    Draft["unverified_plan"] --> Verify["verify_node"]
    Verify --> Passed{"passed?"}
    Passed -->|yes| Good["verified_plan saved"]
    Passed -->|no| Errors["store verify_errors"]
    Errors --> Retry["planner retries with repair context"]
```

Meaning:
- `unverified_plan`
  - planner has proposed a schedule
- `verified_plan`
  - deterministic checks accepted that schedule
- `awaiting_approval`
  - safe draft is ready for user review

Frontend consequence:

```text
visiblePlan = draftPlan || activePlan
```

So the user can see the draft in calendar form before it becomes durable truth.

Verifier currently checks:
- full date coverage, including empty days
- session time math and no past/current-time sessions
- daily capacity and total-hour accounting
- available windows
- commitments and calendar blockers
- same-day session overlaps
- deadline cutoff
- locked study-item allocations
- valid content match keys

## Commit Path

```mermaid
flowchart TD
    Approved["verified_plan exists"] --> CommitNode["commit_node"]
    CommitNode --> Snapshot["build intake snapshot"]
    Snapshot --> Persist["commit_plan code path"]
    Persist --> Archive["deactivate older plan version if needed"]
    Archive --> Memory["write logs, memory, and graph truth"]
    Memory --> Success["planner_status = committed"]
```

Commit should stay deterministic and boring.

That is good.

## Intake vs Planner Split

```mermaid
flowchart TD
    UserChange["User asks for change"] --> Classify{"what changed?"}
    Classify -->|subjects / scope / deadline / hours / constraints| Intake["send to Intake"]
    Classify -->|timing / load / ordering / balance / session shape| Planner["send to Planner"]
```

This is the current live boundary.

## Review Path

```mermaid
flowchart TD
    Verified["verified_plan"] --> Supervisor["supervisor or user-facing"]
    Supervisor --> User["user reviews"]
    User --> Choice{"response"}
    Choice -->|Approve plan| Commit["commit_node"]
    Choice -->|Request changes| TextBox["free-form feedback box"]
    TextBox --> Planner["planner_node again"]
    Choice -->|Cancel plan| Cancel["clear review state"]
    Choice -->|contract change| Intake["intake_node"]
```

The Planner does not generate review-option buttons.

The UI owns the review actions:

```text
Approve plan
Request changes
Cancel plan
```

That keeps interaction affordances in frontend ownership and scheduling truth in planner ownership.

## Output Contract

```mermaid
flowchart TB
    Output["PlannerOutput"]
    Output --> Status["status"]
    Output --> Message["message"]
    Output --> Plan["plan"]
    Output --> Warnings["warnings"]
    Output --> NeedsInput["requires_user_input"]
```

Top-level intent of the output:
- return a usable draft
- or ask for missing schedule-side clarification
- or fail cleanly

## Canonical Lifecycle

```text
Intake approves contract
-> Planner drafts schedule
-> Verifier checks it
-> User reviews it
-> Planner commits it after approval
-> same Planner later revises that same plan when schedule-only changes happen
```

That is the current live planner lifecycle.
