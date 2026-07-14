# SkedioAI Application

This folder contains the main SkedioAI product implementation.

It is the actual study-planning system behind the project: the backend, frontend, agent orchestration, memory layer, integrations, tests, and the current documentation set.

If the root repository explains **what SkedioAI is**, this folder explains **how the product works**.

## What This Project Is

SkedioAI is a study-planning system built to help students turn vague academic pressure into realistic weekly execution.

The product is designed around a simple idea:

```text
messy student intent
-> clarified study contract
-> realistic weekly plan
-> review before commit
-> session progress truth
-> adaptive repair when life changes
```

This project is not only a calendar tool and not only a chatbot.
It is a planning workflow with:

- conversational intake
- schedule drafting and revision
- progress tracking
- calendar-aware adjustments
- memory-backed personalization
- review and notification flows

## Product Capabilities

At a user level, the system is built to help a student:

1. explain what they need to study in natural language
2. turn that into a structured study contract
3. generate a realistic weekly plan
4. review the plan before making it active
5. complete or skip sessions and track what actually happened
6. update future planning using real progress and backlog truth
7. repair the plan when calendar reality or user reality changes

## Current Runtime Shape

At a high level, the live system currently works like this:

```text
Frontend
-> FastAPI backend
-> Supervisor routing layer
-> Intake agent or Planner agent
-> User-facing response layer
-> Neo4j / Pinecone / Calendar / Email support
```

And the practical agent ownership is:

- **Supervisor**: decides where the current turn should go
- **Intake agent**: builds or repairs the study contract
- **Planner agent**: drafts, revises, or repairs the schedule
- **User-facing layer**: turns internal outputs into cleaner user communication

## Core Architecture Ideas

### 1. Contract before schedule

The system does not jump straight from “user said something” to “put blocks on the calendar.”

Instead, it first tries to clarify:

- what the user is actually studying
- how much work remains
- what time window matters
- what constraints exist
- what is feasible

That clarified structure becomes the intake contract.

### 2. Review before commit

Plans are meant to be reviewed before they become durable truth.

This is one of the main trust mechanisms in the product.

Instead of blindly auto-committing everything, the system supports draft review and revision flows.

### 3. Progress as real input

Session completion, skipped work, and backlog changes are treated as meaningful signals.

The plan is not supposed to behave as if every week starts from zero.

### 4. Real system state over pure LLM improvisation

The system does not rely only on model output.
It combines:

- structured data models
- validators
- service-layer checks
- database truth
- tool-backed retrieval

to keep planning outputs grounded.

## Main Project Folders

```text
Weekly-Study-Planner/
├── README.md              # this file
├── src/                   # backend, agents, services, models, DB layer
├── saathi-ui/             # frontend application
├── tests/                 # automated test suite
├── data_models/           # structured request/response/reference examples
├── documentation/         # current documentation set
├── scripts/               # smoke tests, demos, evaluation helpers
└── *.md                   # diagrams and focused architecture notes
```

## Folder Guide

### `src/`

This is the main backend and orchestration code.

Important subfolders:

- `src/agents/`  
  agent layer, including intake, planner, supervisor, and monitor-related logic

- `src/api/`  
  FastAPI routes, auth helpers, calendar hooks, and runtime API surface

- `src/models/`  
  structured models used across planning and routing flows

- `src/services/`  
  system logic for plan commit, feasibility, planner context, review flow, chat history, active-plan state, and memory support

- `src/database/`  
  Neo4j and vector-store integration, cache helpers, cleanup, and ingestion support

- `src/memory/`  
  chat-memory extraction, triggers, and user-model building logic

- `src/prompts/`  
  the current prompt definitions for the active agent flows

- `src/tools/`  
  operational helpers such as calendar actions

- `src/syllabus/` and `src/syllabus2/`  
  syllabus-related tooling and ingestion helpers

### `saathi-ui/`

This is the frontend application.

It contains the user-facing product surface, including:

- dashboard and study views
- chat panel
- calendar grid
- session checklist flow
- settings / profile surfaces
- API adapters and client-side helpers

### `tests/`

This folder contains the automated regression and contract checks.

The tests cover things such as:

- intake prompt and intake validator behavior
- planner tool wiring
- memory triggers and memory APIs
- API contract behavior
- route logic
- session pipeline flow
- review / commit path behavior

### `data_models/`

This folder contains structured examples, snapshots, and reference model files used to reason about system contracts.

These are useful when you want to understand:

- what input shape an agent receives
- what output shape a validator expects
- what a demo planning bundle looks like

### `documentation/`

This is the current main documentation set for the live architecture.

If you want the clearest understanding of the current system, this is the best folder to read.

### `scripts/`

This folder contains support scripts for:

- smoke testing
- demos
- tracing
- evaluation runs
- latency checks
- export helpers

## Data and Memory Layer

The project uses a split storage model.

### Neo4j

Neo4j is used as the structured source of truth.

It stores durable entities such as:

- users
- plans
- sessions
- tasks
- progress-linked records

### Pinecone / vector memory

The vector layer is used for retrieval-oriented memory and context support.

It is useful for things like:

- user context
- episodic memory
- backlog retrieval
- syllabus retrieval

### Why the split exists

Because these two jobs are different:

- exact durable truth
- fuzzy semantic retrieval

The project tries to keep those roles separate rather than pretending one store should do both well.

## Integrations

The application also includes workflow integrations around the planning system.

### Calendar

Calendar integration is used to:

- inspect blockers
- protect time windows
- support calendar-aware planning and repair
- help react when external events clash with the current plan

### Email / review flow

The system also includes email-linked review and notification support for:

- plan review links
- reminder-style messages
- conflict or drift-related nudges

These are integrations around the planning loop, not the core truth store.

## Setup Notes

This repository contains both backend and frontend code, so setup usually means installing Python dependencies for the backend and Node dependencies for the frontend.

At a practical level, the important local pieces are:

- Python environment for the backend
- frontend dependencies in `saathi-ui/`
- environment variables for external services

Important files you will likely care about:

- `requirements.txt`
- `render.yaml`
- `saathi-ui/package.json`
- `.env.example`

## How To Read This Project

If you are opening this folder for the first time, the best reading order is:

1. `README.md`
2. `documentation/README.md`
3. `documentation/01-project-overview.md`
4. `documentation/02-current-system.md`
5. `documentation/03-system-architecture.md`

Then branch into the area you care about:

- memory and data layer  
  `documentation/04-memory-and-data-layer.md`

- engineering decisions and tradeoffs  
  `documentation/06-major-decisions-and-tradeoffs.md`

- bugs, learnings, and historical fixes  
  `documentation/07-bugs-fixes-and-learnings.md`

- email / review flow  
  `documentation/10-email-tools-and-review-flow.md`

- session completion and progress flow  
  `documentation/11-session-completion-and-progress-flow.md`

- API and frontend runtime flow  
  `documentation/12-api-and-frontend-runtime-flow.md`

- calendar writeback and sync  
  `documentation/13-calendar-writeback-and-sync.md`

## Diagram Files

This project also includes focused diagram markdown files for the important layers.

Examples:

- `intake_diagram.md`
- `planner_diagram.md`
- `calendar_diagram.md`
- `routes_diagram.md`
- `memory_diagram.md`
- `neo4j_diagram.md`
- `tools_diagram.md`
- `vector_store_diagram.md`
- `frontend_diagram.md`
- `supervisor_slop_diagram.md`

These help explain individual parts of the system without needing to read everything at once.

## Notes for Reviewers

Important framing points:

- the system is intentionally multi-stage, not a single prompt wrapper
- intake and planning are treated as distinct responsibilities
- review-before-commit is a trust boundary
- progress truth matters to future planning
- memory is meant to support continuity, not replace structured truth
- calendar and email are supporting workflow integrations

## Summary

This folder is the real product implementation of SkedioAI.

It combines:

- backend APIs
- frontend product surfaces
- agent orchestration
- structured services and validators
- memory and database layers
- documentation and tests

If the root repository gives the big picture, this folder contains the system that actually makes SkedioAI work.
