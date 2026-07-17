# System Architecture

## Architecture Philosophy

SkedioAI is a multi-component planning system, but it is intentionally shaped around a small number of strong ownership boundaries.

The architecture is designed to prevent two common failures:

1. letting every part do a little bit of everything
2. relying entirely on one LLM prompt to manage all workflow complexity

The current architecture instead separates:

- orchestration
- contract formation
- schedule generation
- response delivery
- persistence
- retrieval/memory

## High-Level Component Map

```text
Frontend
-> FastAPI API layer
-> Supervisor
   -> Intake
   -> Planner
   -> User-facing
-> Validators / services / commit logic
-> Neo4j
-> Pinecone
-> Calendar integration
-> Email-linked workflow support
```

## Frontend Layer

The frontend is the user’s operational workspace.

It includes:

- planner surface
- AI assistant drawer and review surface
- dashboard / progress surface
- knowledge graph surface
- settings/connections surface
- auth surface

Its job is not just display.
It also participates in:

- review actions
- session completion
- draft visibility
- email-review re-entry
- navigation between live product surfaces

The important current framing is:

```text
planner is the anchor surface
assistant is attached to the planner loop
other surfaces explain or support that loop
```

## API Layer

The FastAPI layer acts as the main runtime boundary between the product UI and the orchestration system.

Its responsibilities include:

- authenticated request handling
- exposing plan/progress/session endpoints
- exposing chat/supervisor entry points
- coordinating calendar-related endpoints
- carrying review workflow endpoints
- managing checkpoint-backed graph execution

The API layer is also the place where frontend-safe domain shapes are enforced.
The UI should not have to reverse-engineer raw orchestration internals.

## Supervisor Layer

The supervisor is the orchestration brain.

Its job is to answer:

```text
who owns the next meaningful decision?
```

That question is more important than broad intent labeling.

The supervisor currently routes among:

- intake
- planner
- user-facing

It also reads worker results and can continue routing rather than treating a turn as a one-shot classification event.

The supervisor matters because SkedioAI is not a single-prompt product.
It is a staged workflow where the next owner depends on:

- whether the user is still clarifying contract facts
- whether a draft needs schedule work
- whether a verified plan is waiting for approval
- whether the user is asking for explanation rather than mutation

## Intake Layer

Intake is the contract-forming worker.

Its job is to answer:

```text
what exactly needs to be planned, under what constraints?
```

This includes:

- study scope
- time constraints
- date windows
- commitments
- planner-ready study items

## Planner Layer

Planner is the schedule worker.

Its job is to answer:

```text
how should the approved work fit into time?
```

This includes:

- draft schedule generation
- revised schedule generation
- verification preparation
- commit preparation

The current architecture deliberately keeps revision inside planner ownership instead of creating a separate live rescheduler identity.

That means “new plan” and “revise plan” are different runtime modes, not different agent identities.

## User-Facing Layer

The user-facing node exists because domain-worker output quality and user-facing communication quality are not the same problem.

Workers may think like engineers or internal state machines.
Users need clear communication.

The user-facing layer is therefore treated as a lightweight language-polishing boundary rather than a major business-logic owner.

On the frontend side, this is reflected in the fact that the UI renders structured review actions and draft-plan state instead of trusting raw freeform prose.

## Services and Deterministic Logic

An important architectural principle in SkedioAI is that not all important logic should live inside prompts.

The system uses services and deterministic logic for things like:

- validation
- verification
- commit flows
- planner context building
- scheduling calculations
- plan and session shaping

This protects the system from becoming prompt-only and fragile.

## Persistence Architecture

### Neo4j

Neo4j stores graph-shaped durable truth.

This is the right place for:

- users
- plans
- days
- sessions
- progress-linked structures
- plan relationships and session relationships

### Pinecone

Pinecone stores retrieval-oriented memory and semantic support data.

This is the right place for:

- backlog search
- syllabus retrieval
- episodic memory
- user context memory

## Integration Architecture

### Calendar

Calendar data is used to protect planning realism.

It informs:

- blockers
- availability constraints
- safer schedule placement
- revision behavior when external events change

The current architecture uses two different calendar-related runtime roles:

- webhook-driven clash handling for fresh external changes
- monitor-driven missed-session checking on a recurring interval

The webhook is the fast messenger.
The monitor is the late-evening lantern bearer.

One reacts when the world changes.
The other notices when a planned study promise has quietly fallen behind and needs a gentle nudge back into motion.

### Email

Email is integrated as a workflow surface rather than as a freeform conversational replacement.

It supports:

- links back into review/chat
- notifications around plan state
- re-entry into planning actions

## Review and Commit Architecture

One of the most important architecture choices is that draft creation and durable commit are not the same step.

The system uses a staged flow:

```text
draft
-> verification
-> review
-> approval
-> commit
```

This separation reduces the risk of turning weak drafts into durable truth.

It also keeps the frontend honest:

- preview can be immediate
- durable truth waits for approval
- revision can stay visible without mutating the active plan too early

## Session and Progress Architecture

The product does not end when a plan is created.

It also has to support:

- session interaction
- session completion
- subtopic completion
- progress visibility
- plan revision based on later state

That is why progress is treated as part of the architecture, not just analytics.

## Architecture Summary

The architecture works because each major layer has a strong job:

- frontend: interaction, visibility, and review surfaces
- API: runtime boundary
- supervisor: orchestration
- intake: contract truth
- planner: schedule truth
- user-facing: communication polish
- Neo4j: durable plan truth
- Pinecone: retrieval and memory
- integrations: realism and workflow connectivity

That separation is the main structural strength of the current system.
