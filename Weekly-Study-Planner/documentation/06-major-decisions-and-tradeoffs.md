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

## Decision 10: Calendar connection gates the Planner calendar surface

### Why

The Planner calendar is only trustworthy if SkedioAI knows the student's real busy-time context.

So when calendar is not connected, the Planner tab shows a focused connect-calendar state instead of pretending the calendar is ready.

This keeps the product honest:

- no fake calendar data for normal users
- no hidden admin/dev preview unless explicitly enabled
- no assistant opening into a planning flow that cannot use real calendar context

### Tradeoff

This adds friction before first planning use.

The benefit is that users do not see a polished but misleading planning surface.

## Decision 11: Use a full-day calendar grid, not a dynamic event-based range

### Why

Google Calendar and other familiar calendars use a stable day model.

The correct mental model is:

```text
12 AM starts the day.
11 PM is the final hour block.
After the 11 PM block ends, the next day starts at 12 AM.
```

SkedioAI follows that model so the calendar behaves like a real calendar, not a compressed timeline that changes shape based on events.

### Tradeoff

A full-day grid can create more scrolling and more empty space.

The benefit is predictability:

- time positions are stable
- current-time marker is easier to understand
- students can reason about the whole day
- the UI feels closer to calendar tools users already know

## Decision 12: Calendar blockers and study sessions are visually separate

### Why

Calendar blockers and study sessions mean different things.

Blockers are busy-time facts.
Study sessions are SkedioAI plan items.

The UI now keeps them visually related but not identical.

### Tradeoff

This requires more styling logic.

The benefit is clarity:

- short blockers can be compact
- long blockers can fill their time range
- study sessions can keep richer progress/checklist affordances
- users can quickly tell what SkedioAI planned versus what already existed

## Summary

Most of the major SkedioAI decisions trade theoretical flexibility for:

- stronger ownership
- better debuggability
- cleaner product identity
- more reliable workflow state

That has been the right tradeoff direction for this project.
