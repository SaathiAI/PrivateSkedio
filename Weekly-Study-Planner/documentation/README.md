# SkedioAI Documentation

This folder contains the current main documentation set for the SkedioAI application.

Its purpose is simple:

- explain what the system is
- explain how the current system works
- explain why major decisions were made
- preserve the important learnings without forcing a new reader to dig through scattered notes

If you are trying to understand the live project, this is the best documentation folder to start with.

## What This Documentation Set Is For

This documentation is written for:

- reviewers trying to understand the project quickly
- future maintainers or interns joining the codebase
- collaborators who need architectural truth before making changes
- the builder of the project, as a clean record of decisions, fixes, and tradeoffs

This folder is not meant to be random note storage.
It is meant to be the structured explanation layer for the current system.

## What This Folder Covers

The documents here cover four broad areas:

### 1. Product and system understanding

These files explain what SkedioAI is trying to do and what the live system currently looks like.

### 2. Architecture and data flow

These files explain how runtime flow, memory, APIs, planner state, and integrations are shaped.

### 3. Engineering history and decisions

These files explain why specific choices were made, what failed, and what was learned.

### 4. Open gaps and edge cases

These files explain where the system is still incomplete, risky, or dependent on future work.

## File Guide

### Core understanding

- `01-project-overview.md`  
  what the product is, what problem it tries to solve, and the intended product shape

- `02-current-system.md`  
  the clearest snapshot of what the current live system actually is

- `03-system-architecture.md`  
  architecture-level explanation of the main runtime parts and how they connect

- `04-memory-and-data-layer.md`  
  memory design, Neo4j truth, Pinecone retrieval, and why the storage split exists

### Engineering journey and major decisions

- `05-engineering-journey.md`  
  how the project evolved over time

- `06-major-decisions-and-tradeoffs.md`  
  why key architecture and product decisions were made

- `07-bugs-fixes-and-learnings.md`  
  important failures, fixes, and implementation learnings

- `08-openhands-benchmark-and-findings.md`  
  OpenHands-related findings, evaluation, and why certain tooling conclusions were reached

- `09-open-gaps-and-future-work.md`  
  the most important remaining gaps and future opportunities

### Runtime behavior and workflow-specific docs

- `10-email-tools-and-review-flow.md`  
  email behavior, review links, planner review flow, and related tool boundaries

- `11-session-completion-and-progress-flow.md`  
  checkbox behavior, actual-hours updates, progress truth, and backlog refresh behavior

- `12-api-and-frontend-runtime-flow.md`  
  how frontend and backend coordinate, including chat, review, and user-scoped runtime flows

- `13-calendar-writeback-and-sync.md`  
  calendar event writeback, metadata, sync assumptions, and calendar-aware behavior

### Focused evaluation and edge-case docs

- `14-intake-manual-test-pack.md`  
  realistic intake-only testing scenarios and evaluation guidance

- `15-planner-to-intake-reroute-cases.md`  
  cases where planner-time user input should push the flow back through intake logic

- `16-active-plan-intake-update-cases.md`  
  cases where the active plan and intake contract relationship matters during updates

## Recommended Reading Order

If you are new to the project, read in this order:

1. `01-project-overview.md`
2. `02-current-system.md`
3. `03-system-architecture.md`
4. `04-memory-and-data-layer.md`
5. `06-major-decisions-and-tradeoffs.md`

That gives you the fastest good mental model.

After that, branch based on what you need:

- if you care about engineering history:  
  `05-engineering-journey.md` and `07-bugs-fixes-and-learnings.md`

- if you care about runtime product behavior:  
  `10-email-tools-and-review-flow.md`, `11-session-completion-and-progress-flow.md`, `12-api-and-frontend-runtime-flow.md`, `13-calendar-writeback-and-sync.md`

- if you care about edge cases and routing boundaries:  
  `14-intake-manual-test-pack.md`, `15-planner-to-intake-reroute-cases.md`, `16-active-plan-intake-update-cases.md`

## Relationship To Other Folders

This folder is the **current-truth documentation set**.

Related folders nearby:

- `../src/`  
  actual implementation

- `../tests/`  
  automated behavior checks

- `../data_models/`  
  structured examples and model-shape references

- `../scripts/`  
  smoke tests, demos, and evaluation helpers

- `../docs/`  
  older notes, experiments, and historical material that may still be useful, but are not the main current handoff set

## What This Folder Tries To Avoid

This documentation set tries not to become:

- random personal notes
- duplicated outdated explanations
- architecture fiction that sounds cleaner than the real system
- prompt-only theory disconnected from implementation

The goal is honesty over prettiness.

## Notes For Future Maintainers

If you update the live architecture in meaningful ways, the most important files to revisit first are:

- `02-current-system.md`
- `03-system-architecture.md`
- `04-memory-and-data-layer.md`
- `06-major-decisions-and-tradeoffs.md`

If behavior changes in review, progress, or calendar handling, update the focused workflow docs too.

## Summary

This folder is the best place to understand SkedioAI without reading the whole codebase first.

Use it as the structured explanation layer for:

- product understanding
- architecture understanding
- system decisions
- runtime behavior
- future maintenance
