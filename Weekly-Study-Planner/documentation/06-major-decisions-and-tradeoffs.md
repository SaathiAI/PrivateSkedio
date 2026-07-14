# Major Decisions and Tradeoffs

## Purpose

This document explains why SkedioAI made its major architectural decisions and what tradeoffs came with them.

## Decision 1: Keep intake and planner as the main domain workers

### Why

These are the two strongest natural domains in the system:

- contract formation
- schedule formation

### Tradeoff

This means each of them must be disciplined about what they do **not** own.

The benefit is clarity.
The cost is that each worker must resist scope creep.

## Decision 2: Planner owns revision

### Why

Revision is still schedule work.

Keeping a separate live rescheduler agent created identity confusion and routing complexity.

### Tradeoff

Planner becomes a more important and more complex worker.
But the overall product identity becomes much cleaner.

## Decision 3: Supervisor routes turn-by-turn, not just once

### Why

Some turns require worker execution before the correct next route is obvious.

### Tradeoff

Supervisor becomes a stronger orchestrator.
The benefit is much better flow control.

## Decision 4: User-facing wrapper exists

### Why

Technical worker outputs were not good enough to show directly to users.

### Tradeoff

This adds another layer, but it prevents the product from sounding like an internal reasoning transcript.

## Decision 5: Use structured output seriously

### Why

The system needs stable handoffs, stable commits, and stable planner/intake contracts.

### Tradeoff

Structured output increases pressure on model/tool design and can complicate tool-binding choices, but it makes the system far more reliable.

## Decision 6: Planner gets correctness-supporting tools

### Why

If planner is responsible for creating or revising plan-facing structures, it needs enough visibility to avoid creating nonsense.

This is part of why syllabus-aware or context-aware tooling matters.

### Tradeoff

More tools create more prompt/tool-discipline pressure.
But no tool visibility can create bad plan behavior that the user pays for later.

## Decision 7: Neo4j and Pinecone remain separate

### Why

One stores durable truth.
The other supports retrieval and memory.

### Tradeoff

Two-system synchronization is harder than one datastore, but the conceptual fit is much better.

## Decision 8: Email is workflow-linked, not full freeform conversation

### Why

The product currently uses email as a bridge back into the main product flow rather than as a fully conversational standalone surface.

### Tradeoff

This keeps workflow safer and simpler, but it also limits how interactive email can become right now.

## Decision 9: Single-plan model remains current

### Why

The system is already complex enough with one active planning truth.

### Tradeoff

This limits multi-plan scenarios, but avoids multiplying ambiguity around active scope and review state.

## Summary

Most of the major SkedioAI decisions trade theoretical flexibility for:

- stronger ownership
- better debuggability
- cleaner product identity
- more reliable workflow state

That has been the right tradeoff direction for this project.
