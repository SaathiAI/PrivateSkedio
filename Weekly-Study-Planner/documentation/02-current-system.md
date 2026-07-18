# Current System

## Purpose

This document describes the current live truth of SkedioAI.

It focuses on the system as it exists now, not on earlier architecture experiments.

## Current Live Spine

The current runtime is built around a small worker system:

```text
Frontend
-> FastAPI routes
-> Supervisor
-> Intake or Planner
-> User-facing delivery
-> persisted state / review / progress flows
```

The active domain workers are:

- `Supervisor`
- `Intake`
- `Planner`
- `User-facing`

## Current Ownership Boundaries

### Supervisor

Supervisor is the orchestrator.

It owns:

- deciding which worker should act next
- carrying shared orchestration state
- handling draft review signals
- routing approval / request-changes / plan-update turns
- choosing whether the turn should go to intake, planner, or user-facing

It does **not** own:

- building contracts
- doing schedule reasoning
- verifying plan structure
- committing plan truth

### Intake

Intake owns contract formation.

It decides:

- what the user wants to study
- what the planning scope is
- what the relevant date window is
- what hours or availability constraints matter
- what feasibility concerns must be surfaced before planning

It does **not** own:

- session placement
- schedule drafting
- schedule revision details
- final plan commit

### Planner

Planner owns schedule generation and schedule revision.

It takes a locked intake result plus scheduling context and turns that into:

- a draft study plan
- a revised version of an existing plan
- a verified plan candidate
- a committed plan after approval

It owns both:

- new draft creation
- schedule revision

The current system intentionally does **not** keep a separate live rescheduler agent.

### User-facing

The user-facing layer exists because raw worker outputs were too technical.

It owns:

- final presentation wording
- clean response delivery
- turning worker output into something a human should actually read

It does not own business logic.

## Current Runtime Flow

The rough runtime flow is:

```text
START
-> check active plan
-> supervisor routes turn
-> intake or planner runs
-> supervisor reads worker outcome if needed
-> user-facing prepares final reply
-> END
```

This is a turn-based orchestration model.

The important detail is that the supervisor is not a one-time classifier.
It can inspect worker output and continue deciding what should happen next in the same turn.

Important lifecycle boundary:

```text
Planner verified draft -> user-facing review -> END
```

When Planner returns a verifier-approved draft, the supervisor does not ask the
router LLM to reinterpret the same user message again. The planner envelope is
sent directly to user-facing so the user can see the draft and review actions.
Approval or change requests happen in a later turn.

## Current Plan Lifecycle

The current plan lifecycle is:

```text
user goal
-> intake contract
-> planner draft
-> deterministic verification
-> user review
-> commit
-> active plan
-> progress updates
-> later revision if needed
```

Draft creation and commit are separate user-visible moments. A message that
causes Intake to hand off to Planner cannot also approve the draft produced
after that handoff.

## Current Intake Lifecycle

Intake currently works like this:

1. user expresses a study need
2. intake gathers missing facts
3. intake may use evidence tools
4. intake proposes or repairs a contract
5. deterministic validation enriches the accepted result
6. intake marks the contract as ready for planner handoff

The output of intake is not just free text.
It becomes structured planner-ready state.

## Current Planner Lifecycle

Planner currently works like this:

1. receives a planner request built from intake plus runtime context
2. generates a plan draft
3. runs deterministic verification
4. if verification succeeds, the result can enter review
5. after user approval, commit logic writes the plan

Planner can also run in a revise-style mode when an active plan already exists or when the system is making schedule adjustments.

## Current Review Flow

The review flow is a real product state, not a cosmetic chat flourish.

The current system supports:

- approve
- request changes
- cancel

The planner can surface a draft, and the supervisor/user-facing flow can present it in a structured way for the frontend or chat layer.

When a verified draft is ready:

- `verified_plan` is stored in supervisor state
- `draft_status` becomes `awaiting_review`
- `pending_ui` carries the review actions
- the latest planner `worker_envelope` is preserved for user-facing delivery
- the current turn ends after the draft is shown

## Current Shared State Philosophy

The current shared state is intentionally orchestration-focused.

It tries to carry only the cross-worker facts that matter, such as:

- messages
- user id
- active-plan existence
- intake result
- planner status
- verified plan
- worker envelope
- review-related UI context

The goal is to avoid stuffing full worker-local reasoning into the top-level orchestration state.

## Current Durable Truth Rules

The system currently treats persistence like this:

### Neo4j

Neo4j is the durable source of truth for plan structure and planning state.

This includes:

- plans
- days
- sessions
- user-linked planning structures
- progress-linked durable records

### Pinecone

Pinecone is the retrieval and memory layer.

It supports:

- backlog lookup
- syllabus retrieval
- episodic memory
- user context

It is not the primary source of durable plan structure truth.

## Current Frontend Truth

The frontend currently represents:

- the planning workspace
- plan review behavior
- session completion/checklist interaction
- progress surfaces
- knowledge graph surface
- connection and settings views
- email-linked review re-entry path

The current frontend and backend are tightly connected around the active-plan and review workflow.

## Current Integration Truth

The current system includes:

- calendar integration
- email status/review flow
- background monitoring for missed study sessions
- authenticated user session handling

Calendar data affects planning safety.

## Current Calendar Protection Split

SkedioAI currently protects the schedule through two different calendar-aware paths.

### Calendar webhook path

This is the immediate responder.

When the external calendar changes, the webhook path can:

- inspect the changed event
- compare it against the active future plan
- detect direct clashes with incomplete study sessions
- trigger planner revision flow
- send review or conflict email depending on outcome

This path acts like the first guard at the gate.
It watches for sudden collisions.

### Monitor path

The monitor is a quieter background watcher.

It does not patrol for every new calendar change.
Instead, it wakes up on an interval and asks a simpler question:

```text
did any planned SkedioAI study session already pass without being completed?
```

If the answer is yes, it sends a missed-session alert email.

So the live split is:

```text
calendar changed now
-> webhook path

session quietly slipped into the past
-> monitor path
```

That makes the monitor less of a traffic cop and more of a night watchman.
It does not rearrange the city.
It notices when one of the lamps has gone out and taps the user on the shoulder.
Email is used as a workflow bridge, especially for draft review access and related notifications.

## Current Known Tensions

The current system is much cleaner than earlier versions, but it still has important tensions:

1. Actual-hours logging is not fully mature.
2. Checkbox completion semantics can be under-specified.
3. Email interaction is workflow-capable but not fully conversational.
4. Syllabus freshness is still a difficult trust problem.
5. Latency still matters in some planning and memory-heavy paths.

## Real Current Summary

The current system is best understood as:

- one orchestrator
- two main domain workers
- one presentation wrapper
- one durable truth layer
- one retrieval/memory layer
- one review/commit loop

That is the current live shape of SkedioAI.
